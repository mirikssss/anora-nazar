"""Приём событий активности: дубли, конфликты, исправления и отмены по контракту; новые совпадения — уведомления
подписанным кредиторам в той же транзакции (outbox)."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from network_operator.modules.activity import domain, repository
from network_operator.modules.activity.domain import EventVersion, Span, TokenKey
from network_operator.modules.activity.models import ActivityEventRow
from network_operator.modules.activity.schemas import ActivityIn, ActivityOut
from network_operator.modules.clients.domain import Caller
from network_operator.modules.quotas import service as quotas
from network_operator.modules.watches import service as watches
from shared.contracts.network import ActivityEvent
from shared.errors import ForbiddenError

Outcome = Literal["accepted", "duplicate", "conflict", "unknown_reference"]


@dataclass
class _Tally:
    accepted: int = 0
    duplicates: int = 0
    conflicts: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)

    def add(self, event_id: str, outcome: Outcome) -> None:
        if outcome == "accepted":
            self.accepted += 1
        elif outcome == "duplicate":
            self.duplicates += 1
        elif outcome == "conflict":
            self.conflicts.append(event_id)
        else:
            self.unknown.append(event_id)


@dataclass(frozen=True)
class _Intake:
    lender: str
    realm_id: UUID | None
    now: datetime
    history: bool

    def received_at(self, event: ActivityEvent) -> datetime:
        return event.received_at if self.history and event.received_at is not None else self.now


def ingest(session: Session, caller: Caller, realm_id: UUID | None, body: ActivityIn, now: datetime) -> ActivityOut:
    if caller.lender is None:
        raise ForbiddenError("lender_required", "События присылает только кредитор")
    if not caller.history and any(e.received_at is not None for e in body.events):
        raise ForbiddenError("history_required", "received_at в событии — только для прогона истории (право history)")
    intake = _Intake(caller.lender, realm_id, now, caller.history)
    tally = _Tally()
    for event in body.events:
        tally.add(event.event_id, _one(session, intake, event))
    quotas.log(session, caller, realm_id, now, operation="activity", items=len(body.events), tokens=0)
    return ActivityOut(
        accepted=tally.accepted,
        duplicates=tally.duplicates,
        conflicts=tally.conflicts,
        unknown_references=tally.unknown,
    )


def _repeat(existing: ActivityEventRow, digest: str) -> Outcome:
    return "duplicate" if existing.content_hash == digest else "conflict"


def _one(session: Session, intake: _Intake, event: ActivityEvent) -> Outcome:
    digest = domain.content_hash(event)
    received_at = intake.received_at(event)
    root, versions = None, []
    if event.refers_to is not None:
        root = _root(session, intake, event.refers_to)
        # блокировка версий раньше проверки на дубль: параллельный повтор того же исправления ждёт и видит дубль
        versions = [] if root is None else repository.versions(session, root.id)
    existing = repository.find(session, intake.lender, intake.realm_id, event.event_id)
    if existing is not None:
        return _repeat(existing, digest)
    if event.refers_to is not None and root is None:
        return "unknown_reference"
    values = _values(intake, event, digest, root) | {"received_at": received_at}
    if event.kind == "correction" and root is not None:
        values |= _correction_span(session, versions, received_at)
    event_pk = repository.insert_event(session, values)
    if event_pk is None:  # параллельный повтор нового события успел раньше
        found = repository.find(session, intake.lender, intake.realm_id, event.event_id)
        return "conflict" if found is None else _repeat(found, digest)
    if root is None:
        repository.set_root(session, event_pk)
    elif event.kind == "retraction":
        repository.retract(session, root.id, received_at)
        return "accepted"
    tokens = domain.event_tokens(event)
    repository.add_tokens(session, event_pk, tokens)
    watches.notify(
        session,
        lender=intake.lender,
        realm_id=intake.realm_id,
        event_root=event_pk if root is None else root.id,
        tokens=tokens,
        occurred_at=event.occurred_at,
        received_at=received_at,
    )
    return "accepted"


def _root(session: Session, intake: _Intake, refers_to: str) -> ActivityEventRow | None:
    """Исходное событие: ссылка на исправление ведёт к его исходному; ссылка на отмену — неизвестна."""
    referred = repository.find(session, intake.lender, intake.realm_id, refers_to)
    if referred is None or referred.fact_kind is None or referred.root_id is None:
        return None
    if referred.root_id == referred.id:
        return referred
    return session.get(ActivityEventRow, referred.root_id)


def _values(intake: _Intake, event: ActivityEvent, digest: str, root: ActivityEventRow | None) -> dict[str, object]:
    fact_kind: str | None = event.kind if event.kind in domain.FACT_KINDS else None
    if event.kind == "correction" and root is not None:
        fact_kind = root.fact_kind
    return {
        "lender": intake.lender,
        "realm_id": intake.realm_id,
        "event_id": event.event_id,
        "kind": event.kind,
        "refers_to": event.refers_to,
        "root_id": None if root is None else root.id,
        "fact_kind": fact_kind,
        "channel": event.channel,
        "subject_token": None if event.subject is None else event.subject.token,
        "credit_share": event.credit_share,
        "occurred_at": event.occurred_at,
        "superseded_at": None,
        "retracted_at": None,
        "content_hash": digest,
    }


def _correction_span(session: Session, versions: list[ActivityEventRow], received_at: datetime) -> dict[str, object]:
    """Новая версия обрезает действовавшую и наследует её конец; отмена события действует и на исправление."""
    placement = domain.place_correction([Span(v.id, v.received_at, v.superseded_at) for v in versions], received_at)
    repository.cut(session, placement.cuts, placement.received_at)
    return {
        "received_at": placement.received_at,
        "superseded_at": placement.superseded_at,
        "retracted_at": versions[0].retracted_at,
    }


def matching(
    session: Session,
    realm_id: UUID | None,
    exclude_lender: str,
    tokens: Sequence[TokenKey],
    occurred_after: datetime,
    received_until: datetime,
) -> dict[TokenKey, list[EventVersion]]:
    """Версии чужих событий по каждому токену — вход чистой функции счётчиков."""
    found: dict[TokenKey, list[EventVersion]] = {}
    if not tokens:
        return found
    for kind, version, token, row in repository.matching(
        session, realm_id, exclude_lender, tokens, occurred_after, received_until
    ):
        found.setdefault((kind, version, token), []).append(
            EventVersion(
                lender=row.lender,
                subject=row.subject_token,
                fact=row.fact_kind or "",
                occurred_at=row.occurred_at,
                received_at=row.received_at,
                valid_until=domain.valid_until(row.superseded_at, row.retracted_at),
            )
        )
    return found


def applications_since(session: Session, lender: str, realm_id: UUID | None, since: datetime) -> int:
    return repository.applications_since(session, lender, realm_id, since)


def totals(session: Session, realm_id: UUID | None) -> dict[tuple[str, UUID | None], tuple[int, int]]:
    return repository.totals(session, realm_id)


def delete_realm(session: Session, realm_id: UUID) -> None:
    repository.delete_realm(session, realm_id)
