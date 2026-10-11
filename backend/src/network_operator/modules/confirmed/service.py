"""Результаты закрытых дел: приём с защитой от повторов и совпадения для ответа счётчиков."""

from collections.abc import Sequence
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from network_operator.modules.clients.domain import Caller
from network_operator.modules.confirmed import domain, repository
from network_operator.modules.confirmed.domain import ConfirmedFact
from network_operator.modules.confirmed.schemas import ConfirmedIn, ConfirmedOut
from network_operator.modules.quotas import service as quotas
from shared.contracts.network import ConfirmedResult
from shared.errors import ForbiddenError

TokenKey = tuple[str, int, str]
Outcome = Literal["accepted", "duplicate", "conflict"]


def accept(session: Session, caller: Caller, realm_id: UUID | None, body: ConfirmedIn, now: datetime) -> ConfirmedOut:
    """Повтор с тем же содержимым — дубль, с другим — конфликт. При прогоне истории результат виден с confirmed_at,
    иначе — с момента получения оператором."""
    if caller.lender is None:
        raise ForbiddenError("lender_required", "Результаты дел присылает только кредитор")
    accepted, duplicates, conflicts = 0, 0, []
    for result in body.results:
        outcome = _one(session, caller.lender, realm_id, result, result.confirmed_at if caller.history else now)
        if outcome == "accepted":
            accepted += 1
        elif outcome == "duplicate":
            duplicates += 1
        else:
            conflicts.append(result.result_id)
    tokens = sum(len(r.tokens) for r in body.results)
    quotas.log(session, caller, realm_id, now, operation="confirmed", items=len(body.results), tokens=tokens)
    return ConfirmedOut(accepted=accepted, duplicates=duplicates, conflicts=conflicts)


def _one(
    session: Session, lender: str, realm_id: UUID | None, result: ConfirmedResult, received_at: datetime
) -> Outcome:
    digest = domain.content_hash(result)
    result_pk = repository.insert_result(
        session,
        {
            "lender": lender,
            "realm_id": realm_id,
            "result_id": result.result_id,
            "typology": result.typology,
            "confirmation": result.confirmation,
            "confirmed_at": result.confirmed_at,
            "received_at": max(received_at, result.confirmed_at),
            "content_hash": digest,
        },
    )
    if result_pk is None:
        return (
            "duplicate" if repository.find_hash(session, lender, realm_id, result.result_id) == digest else "conflict"
        )
    repository.add_tokens(
        session, result_pk, list(dict.fromkeys((t.kind, t.key_version, t.token) for t in result.tokens))
    )
    return "accepted"


def matching(
    session: Session, realm_id: UUID | None, exclude_lender: str, tokens: Sequence[TokenKey], until: datetime
) -> dict[TokenKey, list[ConfirmedFact]]:
    found: dict[TokenKey, list[ConfirmedFact]] = {}
    if not tokens:
        return found
    for kind, version, token, row in repository.matching(session, realm_id, exclude_lender, tokens, until):
        found.setdefault((kind, version, token), []).append(
            ConfirmedFact(row.lender, kind, row.typology, row.confirmation, row.confirmed_at, row.received_at)
        )
    return found


def totals(session: Session, realm_id: UUID | None) -> dict[tuple[str, UUID | None], int]:
    return repository.totals(session, realm_id)


def delete_realm(session: Session, realm_id: UUID) -> None:
    repository.delete_realm(session, realm_id)
