"""Доступ к таблицам модуля."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from bank_sim.modules.personas.models import BankRole


def upsert(session: Session, values: dict[str, Any]) -> None:
    stmt = insert(BankRole).values(**values)
    session.execute(stmt.on_conflict_do_update(index_elements=[BankRole.code], set_=dict(stmt.excluded)))


def all_roles(session: Session) -> list[BankRole]:
    return list(session.scalars(select(BankRole).order_by(BankRole.code)))
