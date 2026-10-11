"""Доступ к таблицам модуля."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from bank_sim.modules.staff.models import Branch, Employee


def upsert(session: Session, model: type[Branch] | type[Employee], values: dict[str, Any]) -> None:
    stmt = insert(model).values(**values)
    session.execute(stmt.on_conflict_do_update(index_elements=["id"], set_=dict(stmt.excluded)))


def branches(session: Session) -> list[Branch]:
    return list(session.scalars(select(Branch).order_by(Branch.id)))


def employees(session: Session) -> list[Employee]:
    return list(session.scalars(select(Employee).order_by(Employee.id)))


def branch(session: Session, branch_id: str) -> Branch | None:
    return session.get(Branch, branch_id)


def employee(session: Session, employee_id: str) -> Employee | None:
    return session.get(Employee, employee_id)
