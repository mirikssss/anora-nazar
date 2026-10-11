"""Приём фактов: новые версии заявок (из событий и из оценок) и события источников.

В той же транзакции, где записан факт, узел находит затронутые открытые заявки и помечает их
«нужна новая оценка». Все затронутые строки блокируются одним запросом по возрастанию id.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from node.modules.applications import service as applications
from node.modules.applications.domain import VersionOutcome
from node.modules.applications.models import Application
from node.modules.audit import service as audit
from node.modules.index import service as index
from node.modules.index.domain import subject_key
from node.modules.ingest import repository
from node.modules.ingest.domain import (
    APPLICATION_CANCELLED,
    APPLICATION_VERSION,
    IngestOutcome,
    classify_entity,
    lag_seconds,
)
from node.modules.ingest.schemas import WatermarkIn
from node.modules.labels import service as labels
from node.modules.outbox import service as outbox
from node.modules.permits import service as permits
from node.modules.policy.domain import Policy
from node.modules.realms.domain import RealmContext
from node.settings import NodeConfig
from shared.clock import Clock
from shared.contracts.application import ApplicationSnapshot
from shared.contracts.facts import FACTS
from shared.errors import ConflictError, ValidationFailedError
from shared.events import EventEnvelope

APPLICATION_ENTITY = "application"


@dataclass(frozen=True)
class IntakeContext:
    policy: Policy
    index_key: bytes
    config: NodeConfig
    clock: Clock


@dataclass(frozen=True)
class AcceptedVersion:
    application: Application
    outcome: VersionOutcome
    marked: list[str]


def _mark(
    session: Session,
    ctx: IntakeContext,
    realm: RealmContext,
    locked: dict[UUID, Application],
    targets: dict[UUID, tuple[str, ...]],
    cause: dict[str, Any],
    trigger: str,
    received_at: datetime,
) -> list[str]:
    """Помечает затронутые заявки своего контура; возвращает их идентификаторы у конвейера."""
    marked = applications.mark_for_reassessment(session, realm.id, set(targets), cause, received_at)
    if not marked:
        return []
    marked_at = ctx.clock.now()
    after_reserve = permits.applications_with_live_permits(session, marked)
    repository.add_metric(
        session,
        {
            "realm_id": realm.id,
            "trigger": trigger,
            "received_at": received_at,
            "marked_at": marked_at,
            "marked_count": len(marked),
            "marked_after_reserve": after_reserve,
        },
    )
    for app_id in marked:
        event = {"application_id": locked[app_id].external_id, "cause": cause, "kinds": list(targets[app_id])}
        outbox.enqueue(session, ctx.config.outbox, realm.id, "application.reassessment_required", event, received_at)
    audit.append(
        session,
        realm.id,
        "application.reassessment_marked",
        {
            "applications": [locked[a].external_id for a in marked],
            "cause": cause,
            "marked_after_reserve": after_reserve,
        },
        received_at,
    )
    return [locked[a].external_id for a in marked]


def accept_application_version(
    session: Session,
    ctx: IntakeContext,
    realm: RealmContext,
    *,
    external_id: str,
    version: int,
    snapshot: ApplicationSnapshot,
    occurred_at: datetime,
    received_at: datetime,
    authoritative: bool,
    trigger: str,
) -> AcceptedVersion:
    subject = subject_key(ctx.index_key, snapshot.applicant.pinfl)
    attrs = index.attributes(snapshot, ctx.index_key)
    app_id = applications.ensure(session, realm.id, external_id, snapshot.channel, subject, received_at)
    linked = index.linked_for_marking(session, realm, app_id, subject, attrs, received_at, ctx.policy)
    open_linked = applications.open_ids(session, realm.id, {link.application_id for link in linked}, received_at)
    locked = applications.lock(session, {app_id} | open_linked)
    app = locked[app_id]
    if app.status != "active":
        raise ConflictError("application_cancelled", "Заявка отменена")
    if app.channel != snapshot.channel or app.subject_key != subject:
        raise ValidationFailedError("application_identity_changed", "Канал или заявитель заявки не меняются")

    result = applications.apply_snapshot(
        session, app, version, snapshot, occurred_at, received_at, authoritative=authoritative
    )
    if result.outcome is not VersionOutcome.APPLIED:
        return AcceptedVersion(app, result.outcome, [])
    index.record_version(session, realm.id, app.id, version, subject, attrs, snapshot, occurred_at, received_at)
    repository.drop_parked_up_to(session, realm.id, APPLICATION_ENTITY, external_id, version)
    targets = {link.application_id: link.kinds for link in linked if link.application_id in locked}
    cause = {"trigger_application": external_id, "trigger_version": version, "received_at": received_at.isoformat()}
    marked = _mark(session, ctx, realm, locked, targets, cause, trigger, received_at)
    return AcceptedVersion(app, result.outcome, marked)


def receive(
    session: Session, ctx: IntakeContext, realm: RealmContext, envelope: EventEnvelope, received_at: datetime
) -> IngestOutcome:
    claimed = repository.claim_event(
        session,
        {
            "realm_id": realm.id,
            "event_id": envelope.event_id,
            "source": envelope.source,
            "type": envelope.type,
            "outcome": "received",
            "received_at": received_at,
        },
    )
    if not claimed:
        return "duplicate"
    outcome = _dispatch(session, ctx, realm, envelope, received_at)
    repository.set_outcome(session, realm.id, envelope.event_id, outcome)
    return outcome


def _dispatch(
    session: Session, ctx: IntakeContext, realm: RealmContext, envelope: EventEnvelope, received_at: datetime
) -> IngestOutcome:
    if envelope.type == APPLICATION_VERSION:
        return _application_version(session, ctx, realm, envelope, received_at)
    if envelope.type == APPLICATION_CANCELLED:
        return _application_cancelled(session, ctx, realm, envelope, received_at)
    return _source_fact(session, ctx, realm, envelope, received_at)


def _application_version(
    session: Session, ctx: IntakeContext, realm: RealmContext, envelope: EventEnvelope, received_at: datetime
) -> IngestOutcome:
    if envelope.entity_type != APPLICATION_ENTITY or envelope.entity_version is None:
        raise ValidationFailedError("invalid_event", "Версия заявки: нужны entity_type=application и entity_version")
    snapshot = ApplicationSnapshot.model_validate(envelope.payload.get("snapshot"))
    accepted = accept_application_version(
        session,
        ctx,
        realm,
        external_id=envelope.entity_id,
        version=envelope.entity_version,
        snapshot=snapshot,
        occurred_at=envelope.occurred_at,
        received_at=received_at,
        authoritative=False,
        trigger=f"event:{envelope.event_id}",
    )
    if accepted.outcome is VersionOutcome.GAP:
        repository.park(
            session,
            {
                "realm_id": realm.id,
                "source": envelope.source,
                "entity_type": APPLICATION_ENTITY,
                "entity_id": envelope.entity_id,
                "version": envelope.entity_version,
                "envelope": envelope.model_dump(mode="json"),
                "received_at": received_at,
            },
        )
        return "parked"
    if accepted.outcome is VersionOutcome.APPLIED:
        _drain(session, ctx, realm, envelope.source, envelope.entity_id, envelope.entity_version + 1, received_at)
        return "applied"
    return "stale"


def _drain(
    session: Session,
    ctx: IntakeContext,
    realm: RealmContext,
    source: str,
    external_id: str,
    next_version: int,
    received_at: datetime,
) -> None:
    """Пришла пропущенная версия — применяем ждавшие следом, по порядку."""
    while (
        parked := repository.take_parked(session, realm.id, source, APPLICATION_ENTITY, external_id, next_version)
    ) is not None:
        envelope = EventEnvelope.model_validate(parked.envelope)
        accept_application_version(
            session,
            ctx,
            realm,
            external_id=external_id,
            version=next_version,
            snapshot=ApplicationSnapshot.model_validate(envelope.payload.get("snapshot")),
            occurred_at=envelope.occurred_at,
            received_at=received_at,
            authoritative=False,
            trigger=f"event:{envelope.event_id}",
        )
        next_version += 1


def _application_cancelled(
    session: Session, ctx: IntakeContext, realm: RealmContext, envelope: EventEnvelope, received_at: datetime
) -> IngestOutcome:
    app_id = applications.find_id(session, realm.id, envelope.entity_id)
    if app_id is None:
        return "stale"
    app = applications.lock(session, {app_id})[app_id]
    if app.status != "active":
        return "stale"
    applications.cancel(app, received_at)
    audit.append(
        session,
        realm.id,
        "application.cancelled",
        {"application_id": envelope.entity_id, "event_id": str(envelope.event_id)},
        received_at,
    )
    return "applied"


def _source_fact(
    session: Session, ctx: IntakeContext, realm: RealmContext, envelope: EventEnvelope, received_at: datetime
) -> IngestOutcome:
    if envelope.entity_version is not None:
        current = repository.entity_version_for_update(
            session, realm.id, envelope.source, envelope.entity_type, envelope.entity_id
        )
        order = classify_entity(None if current is None else current.last_version, envelope.entity_version)
        if order is not VersionOutcome.APPLIED:
            return (
                "stale"
                if order in (VersionOutcome.STALE, VersionOutcome.SAME)
                else _park_fact(session, realm, envelope, received_at)
            )
        repository.save_entity_version(
            session, realm.id, envelope.source, envelope.entity_type, envelope.entity_id, envelope.entity_version
        )
    known = FACTS.get(envelope.type)
    if known is not None:
        try:
            known.model_validate(envelope.payload)
        except PydanticValidationError as exc:
            raise ValidationFailedError(
                "invalid_fact",
                f"Факт {envelope.type} не соответствует контракту",
                {"errors": exc.errors(include_url=False, include_context=False)},
            ) from exc
    pinfl = envelope.payload.get("subject_pinfl")
    subject = subject_key(ctx.index_key, str(pinfl)) if pinfl else None
    labels.record_from_fact(
        session, realm.id, envelope.type, envelope.payload, envelope.event_id, envelope.occurred_at, received_at
    )
    repository.add_fact(
        session,
        {
            "realm_id": realm.id,
            "event_id": envelope.event_id,
            "source": envelope.source,
            "type": envelope.type,
            "entity_type": envelope.entity_type,
            "entity_id": envelope.entity_id,
            "subject_key": subject,
            "payload": envelope.payload,
            "occurred_at": envelope.occurred_at,
            "received_at": received_at,
        },
    )
    if subject is not None:
        ids = applications.open_ids_of_subject(session, realm.id, subject, received_at)
        locked = applications.lock(session, set(ids))
        cause = {
            "source": envelope.source,
            "fact": envelope.type,
            "event_id": str(envelope.event_id),
            "received_at": received_at.isoformat(),
        }
        _mark(
            session,
            ctx,
            realm,
            locked,
            {a: ("subject",) for a in locked},
            cause,
            f"event:{envelope.event_id}",
            received_at,
        )
    return "stored"


def _park_fact(session: Session, realm: RealmContext, envelope: EventEnvelope, received_at: datetime) -> IngestOutcome:
    repository.park(
        session,
        {
            "realm_id": realm.id,
            "source": envelope.source,
            "entity_type": envelope.entity_type,
            "entity_id": envelope.entity_id,
            "version": envelope.entity_version,
            "envelope": envelope.model_dump(mode="json"),
            "received_at": received_at,
        },
    )
    return "parked"


def report_watermarks(session: Session, items: list[WatermarkIn]) -> None:
    for item in items:
        repository.upsert_watermark(session, item.model_dump())


def queue_lag_seconds(session: Session, realm_id: UUID, producers: list[str], now: datetime) -> float | None:
    """Наибольшее отставание наблюдаемых производителей; нет отметки — отставание неизвестно (None)."""
    marks = repository.watermarks(session, realm_id, producers)
    if set(producers) - marks.keys():
        return None
    return max(
        (lag_seconds(m.pending_count, m.oldest_pending_occurred_at, m.reported_at, now) for m in marks.values()),
        default=0.0,
    )


def resolve_gap(
    session: Session,
    ctx: IntakeContext,
    realm: RealmContext,
    app: Application,
    version: int,
    snapshot: ApplicationSnapshot,
    occurred_at: datetime,
    received_at: datetime,
) -> None:
    """Ответ владельца на запрос снимка: полный снимок закрывает пропуск версий."""
    accept_application_version(
        session,
        ctx,
        realm,
        external_id=app.external_id,
        version=version,
        snapshot=snapshot,
        occurred_at=occurred_at,
        received_at=received_at,
        authoritative=True,
        trigger=f"snapshot:{app.external_id}:{version}",
    )


def metrics(session: Session, realm_id: UUID) -> dict[str, Any]:
    return repository.metric_summary(session, realm_id)


def latest_fact(
    session: Session,
    realm: RealmContext,
    type_: str,
    as_of: datetime,
    *,
    subject_key: str | None = None,
    entity_id: str | None = None,
) -> dict[str, Any] | None:
    return repository.latest_payload(
        session, realm.visible_ids, type_, as_of, subject_key=subject_key, entity_id=entity_id
    )


def latest_facts_by_subject(
    session: Session, realm: RealmContext, type_: str, subjects: list[str], as_of: datetime
) -> dict[str, dict[str, Any]]:
    return repository.latest_payloads_by_subject(session, realm.visible_ids, type_, subjects, as_of)
