"""Доступ к таблицам модуля."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from bank_sim.modules.scenarios.models import ScenarioRun


def next_number(session: Session, realm_id: UUID) -> int:
    current = session.scalar(select(func.max(ScenarioRun.number)).where(ScenarioRun.realm_id == realm_id))
    return (current or 0) + 1


def add(session: Session, run: ScenarioRun) -> None:
    session.add(run)


def get(session: Session, realm_id: UUID, run_id: UUID, *, lock: bool = False) -> ScenarioRun | None:
    stmt = select(ScenarioRun).where(ScenarioRun.realm_id == realm_id, ScenarioRun.id == run_id)
    if lock:
        stmt = stmt.with_for_update()
    return session.scalars(stmt).one_or_none()


def list_for_realm(session: Session, realm_id: UUID) -> list[ScenarioRun]:
    return list(
        session.scalars(select(ScenarioRun).where(ScenarioRun.realm_id == realm_id).order_by(ScenarioRun.number.desc()))
    )


def remove(session: Session, realm_id: UUID, run_id: UUID) -> None:
    session.execute(delete(ScenarioRun).where(ScenarioRun.realm_id == realm_id, ScenarioRun.id == run_id))
