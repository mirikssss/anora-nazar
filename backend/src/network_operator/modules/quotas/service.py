"""Квота OPRF и журнал запросов: перебор номеров через оператора упирается в число реальных заявок кредитора."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from network_operator.modules.clients.domain import Caller
from network_operator.modules.quotas import domain, repository
from network_operator.modules.quotas.domain import Allowance
from network_operator.modules.quotas.models import RequestLogEntry
from network_operator.settings import QuotasConfig
from shared.errors import TooManyRequestsError

OPRF = "oprf"


def window_start(limits: QuotasConfig, now: datetime) -> datetime:
    return now - timedelta(seconds=limits.window_seconds)


def allowance(
    session: Session, lender: str, realm_id: UUID | None, applications: int, limits: QuotasConfig, now: datetime
) -> Allowance:
    """applications — заявки кредитора в контуре за окно квоты (window_start)."""
    used = repository.used_tokens(session, lender, realm_id, OPRF, window_start(limits, now))
    return domain.allowance(used, applications, limits)


def lock(session: Session, lender: str, realm_id: UUID | None) -> None:
    repository.lock_lender(session, lender, realm_id)


def ensure_oprf_allowance(
    session: Session,
    lender: str,
    realm_id: UUID | None,
    requested: int,
    applications: int,
    limits: QuotasConfig,
    now: datetime,
) -> None:
    current = allowance(session, lender, realm_id, applications, limits, now)
    if not current.admits(requested):
        raise TooManyRequestsError(
            "oprf_quota_exceeded",
            "Квота вычислений OPRF исчерпана: она растёт с числом реальных заявок кредитора",
            {
                "used": current.used,
                "limit": current.limit,
                "requested": requested,
                "window_seconds": current.window_seconds,
            },
        )


def log(
    session: Session,
    caller: Caller,
    realm_id: UUID | None,
    now: datetime,
    *,
    operation: str,
    items: int,
    tokens: int,
    counters: list[str] | None = None,
) -> None:
    repository.add(
        session,
        RequestLogEntry(
            client=caller.client,
            lender=caller.lender,
            realm_id=realm_id,
            at=now,
            operation=operation,
            items=items,
            tokens=tokens,
            counters=counters or [],
            history=caller.history,
        ),
    )


def totals(
    session: Session, realms: list[UUID | None], operation: str
) -> dict[tuple[str | None, UUID | None], tuple[int, int]]:
    return repository.totals(session, realms, operation)


def delete_realm(session: Session, realm_id: UUID) -> None:
    repository.delete_realm(session, realm_id)
