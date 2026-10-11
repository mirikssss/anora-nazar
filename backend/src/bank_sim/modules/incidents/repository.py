"""Доступ к таблицам модуля."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from bank_sim.modules.incidents.models import Incident


def add(session: Session, incident: Incident) -> None:
    session.add(incident)


def list_for_realm(session: Session, realm_id: UUID) -> list[Incident]:
    return list(
        session.scalars(select(Incident).where(Incident.realm_id == realm_id).order_by(Incident.created_at.desc()))
    )
