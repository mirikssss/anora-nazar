"""Доступ к таблицам модуля."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from bank_sim.modules.borrower_app.models import BorrowerApplication


def add(session: Session, record: BorrowerApplication) -> None:
    session.add(record)


def get(session: Session, realm_id: UUID, application_id: str, *, lock: bool = False) -> BorrowerApplication | None:
    stmt = select(BorrowerApplication).where(
        BorrowerApplication.realm_id == realm_id, BorrowerApplication.application_id == application_id
    )
    if lock:
        stmt = stmt.with_for_update()
    return session.scalars(stmt).one_or_none()


def list_for_realm(session: Session, realm_id: UUID, persona_code: str | None) -> list[BorrowerApplication]:
    stmt = (
        select(BorrowerApplication)
        .where(BorrowerApplication.realm_id == realm_id)
        .order_by(BorrowerApplication.created_at.desc())
    )
    if persona_code is not None:
        stmt = stmt.where(BorrowerApplication.persona_code == persona_code)
    return list(session.scalars(stmt))
