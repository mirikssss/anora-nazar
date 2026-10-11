"""Доступ к таблицам модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from node.modules.permits.models import BLOCKING_STATUSES, EXECUTED, RESERVED, UNKNOWN, Hold, Permit


def active_holds(session: Session, application_id: UUID) -> list[Hold]:
    return list(
        session.scalars(
            select(Hold).where(Hold.application_id == application_id, Hold.status == "active").order_by(Hold.created_at)
        )
    )


def statuses_for(session: Session, application_id: UUID, operation_type: str, tranche: int) -> list[str]:
    return list(
        session.scalars(
            select(Permit.status).where(
                Permit.application_id == application_id,
                Permit.operation_type == operation_type,
                Permit.tranche == tranche,
                Permit.status.in_(BLOCKING_STATUSES),
            )
        )
    )


def executed_amount(session: Session, application_id: UUID, operation_type: str, exclude_tranche: int) -> int:
    total = session.scalar(
        select(func.coalesce(func.sum(Permit.amount), 0)).where(
            Permit.application_id == application_id,
            Permit.operation_type == operation_type,
            Permit.tranche != exclude_tranche,
            Permit.status == EXECUTED,
        )
    )
    return int(total or 0)


def by_operation_key(session: Session, realm_id: UUID, operation_key: str, *, lock: bool) -> Permit | None:
    stmt = select(Permit).where(Permit.realm_id == realm_id, Permit.operation_key == operation_key)
    if lock:
        stmt = stmt.with_for_update()
    return session.scalars(stmt).one_or_none()


def expired_reserved(session: Session, now: datetime) -> list[Permit]:
    return list(
        session.scalars(
            select(Permit).where(Permit.status == RESERVED, Permit.expires_at < now).with_for_update(skip_locked=True)
        )
    )


def unknown(session: Session, limit: int) -> list[Permit]:
    return list(
        session.scalars(
            select(Permit)
            .where(Permit.status == UNKNOWN)
            .order_by(Permit.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )


def count_live(session: Session, application_ids: list[UUID]) -> int:
    if not application_ids:
        return 0
    return int(
        session.scalar(
            select(func.count(func.distinct(Permit.application_id))).where(
                Permit.application_id.in_(application_ids), Permit.status.in_((RESERVED, UNKNOWN, EXECUTED))
            )
        )
        or 0
    )


def counts_by_status(session: Session, realm_id: UUID) -> dict[str, int]:
    rows = session.execute(
        select(Permit.status, func.count()).where(Permit.realm_id == realm_id).group_by(Permit.status)
    )
    return {status: count for status, count in rows}


def executed_applications(session: Session, realm_ids: tuple[UUID, ...], since: datetime) -> set[UUID]:
    """Заявки с исполненным зачислением за период — выданные кредиты (ретро-поиск Т6)."""
    return set(
        session.scalars(
            select(Permit.application_id).where(
                Permit.realm_id.in_(realm_ids),
                Permit.operation_type == "disbursement",
                Permit.status == "executed",
                Permit.reserved_at >= since,
            )
        )
    )
