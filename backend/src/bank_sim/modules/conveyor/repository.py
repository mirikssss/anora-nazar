"""Доступ к таблицам модуля."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from bank_sim.modules.conveyor.models import ConveyorApplication


def add(session: Session, app: ConveyorApplication) -> None:
    session.add(app)


def by_external(
    session: Session, realm_id: UUID, external_id: str, *, lock: bool = False
) -> ConveyorApplication | None:
    stmt = select(ConveyorApplication).where(
        ConveyorApplication.realm_id == realm_id, ConveyorApplication.external_id == external_id
    )
    if lock:
        stmt = stmt.with_for_update()
    return session.scalars(stmt).one_or_none()


def list_for_realm(session: Session, realm_id: UUID) -> list[ConveyorApplication]:
    return list(
        session.scalars(
            select(ConveyorApplication)
            .where(ConveyorApplication.realm_id == realm_id)
            .order_by(ConveyorApplication.created_at.desc())
        )
    )
