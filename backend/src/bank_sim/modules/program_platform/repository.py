"""Доступ к таблицам модуля."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from bank_sim.modules.program_platform.models import AcceptanceActRecord, ProgramHelper, ProgramSupplier


def upsert(session: Session, model: type[ProgramHelper] | type[ProgramSupplier], rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    stmt = insert(model).values(rows)
    key = "id" if model is ProgramHelper else "inn"
    session.execute(stmt.on_conflict_do_update(index_elements=[key], set_=dict(stmt.excluded)))


def helpers(session: Session, district: str | None) -> list[ProgramHelper]:
    stmt = select(ProgramHelper).order_by(ProgramHelper.id)
    if district is not None:
        stmt = stmt.where(ProgramHelper.district == district)
    return list(session.scalars(stmt))


def helper(session: Session, helper_id: str) -> ProgramHelper | None:
    return session.get(ProgramHelper, helper_id)


def suppliers(session: Session, district: str | None, category: str | None) -> list[ProgramSupplier]:
    stmt = select(ProgramSupplier).order_by(ProgramSupplier.inn)
    if district is not None:
        stmt = stmt.where(ProgramSupplier.district == district)
    if category is not None:
        stmt = stmt.where(ProgramSupplier.category == category)
    return list(session.scalars(stmt))


def add_act(session: Session, act: AcceptanceActRecord) -> None:
    session.add(act)


def act(session: Session, realm_id: UUID, act_id: str) -> AcceptanceActRecord | None:
    return session.scalars(
        select(AcceptanceActRecord).where(AcceptanceActRecord.realm_id == realm_id, AcceptanceActRecord.id == act_id)
    ).one_or_none()


def acts(session: Session, realm_id: UUID, application_id: str | None) -> list[AcceptanceActRecord]:
    stmt = (
        select(AcceptanceActRecord)
        .where(AcceptanceActRecord.realm_id == realm_id)
        .order_by(AcceptanceActRecord.created_at.desc())
    )
    if application_id is not None:
        stmt = stmt.where(AcceptanceActRecord.application_id == application_id)
    return list(session.scalars(stmt))
