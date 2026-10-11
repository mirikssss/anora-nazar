"""Доступ к таблицам модуля."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from bank_sim.modules.personas.models import BankRole, BorrowerPersona


def upsert(session: Session, values: dict[str, Any]) -> None:
    stmt = insert(BankRole).values(**values)
    session.execute(stmt.on_conflict_do_update(index_elements=[BankRole.code], set_=dict(stmt.excluded)))


def all_roles(session: Session) -> list[BankRole]:
    return list(session.scalars(select(BankRole).order_by(BankRole.code)))


def upsert_borrower(session: Session, values: dict[str, Any]) -> None:
    stmt = insert(BorrowerPersona).values(**values)
    session.execute(stmt.on_conflict_do_update(index_elements=[BorrowerPersona.code], set_=dict(stmt.excluded)))


def borrowers(session: Session) -> list[BorrowerPersona]:
    return list(session.scalars(select(BorrowerPersona).order_by(BorrowerPersona.birth_date.desc())))


def borrower(session: Session, code: str) -> BorrowerPersona | None:
    return session.get(BorrowerPersona, code)
