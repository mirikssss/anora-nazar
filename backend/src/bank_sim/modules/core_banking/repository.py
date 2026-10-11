"""Доступ к таблицам модуля."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from bank_sim.modules.core_banking.models import Operation


def add(session: Session, operation: Operation) -> None:
    session.add(operation)


def get(session: Session, realm_id: UUID, key: str, *, lock: bool = False) -> Operation | None:
    stmt = select(Operation).where(Operation.realm_id == realm_id, Operation.operation_key == key)
    if lock:
        stmt = stmt.with_for_update()
    return session.scalars(stmt).one_or_none()


def list_for_realm(session: Session, realm_id: UUID) -> list[Operation]:
    return list(
        session.scalars(select(Operation).where(Operation.realm_id == realm_id).order_by(Operation.created_at.desc()))
    )
