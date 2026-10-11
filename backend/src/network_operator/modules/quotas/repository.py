"""Доступ к таблицам модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.orm import Session

from network_operator.modules.quotas.models import RequestLogEntry

Key = tuple[str | None, UUID | None]


def lock_lender(session: Session, lender: str, realm_id: UUID | None) -> None:
    """Проверки квоты одного кредитора в одном контуре идут по очереди — до конца транзакции."""
    session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"oprf:{lender}:{realm_id}"})


def used_tokens(session: Session, lender: str, realm_id: UUID | None, operation: str, since: datetime) -> int:
    realm = RequestLogEntry.realm_id.is_(None) if realm_id is None else RequestLogEntry.realm_id == realm_id
    total = session.scalar(
        select(func.coalesce(func.sum(RequestLogEntry.tokens), 0)).where(
            RequestLogEntry.lender == lender,
            realm,
            RequestLogEntry.operation == operation,
            RequestLogEntry.history.is_(False),
            RequestLogEntry.at > since,
        )
    )
    return int(total or 0)


def add(session: Session, entry: RequestLogEntry) -> None:
    session.add(entry)


def totals(session: Session, realms: list[UUID | None], operation: str) -> dict[Key, tuple[int, int]]:
    """(кредитор, контур) → (число элементов, число токенов) по операции."""
    sandboxes = RequestLogEntry.realm_id.in_([r for r in realms if r is not None])
    realm_filter = or_(sandboxes, RequestLogEntry.realm_id.is_(None)) if None in realms else sandboxes
    rows = session.execute(
        select(
            RequestLogEntry.lender,
            RequestLogEntry.realm_id,
            func.sum(RequestLogEntry.items),
            func.sum(RequestLogEntry.tokens),
        )
        .where(RequestLogEntry.operation == operation, realm_filter)
        .group_by(RequestLogEntry.lender, RequestLogEntry.realm_id)
    )
    return {(r[0], r[1]): (int(r[2]), int(r[3])) for r in rows}


def delete_realm(session: Session, realm_id: UUID) -> None:
    session.execute(delete(RequestLogEntry).where(RequestLogEntry.realm_id == realm_id))
