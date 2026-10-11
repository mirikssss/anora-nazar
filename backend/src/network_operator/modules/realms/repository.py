"""Доступ к таблицам модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from network_operator.modules.realms.models import RealmOutage


def start_outage(session: Session, realm_id: UUID, now: datetime) -> None:
    session.execute(insert(RealmOutage).values(realm_id=realm_id, since=now).on_conflict_do_nothing())


def end_outage(session: Session, realm_id: UUID) -> None:
    session.execute(delete(RealmOutage).where(RealmOutage.realm_id == realm_id))


def in_outage(session: Session, realm_id: UUID) -> bool:
    return session.get(RealmOutage, realm_id) is not None


def outages(session: Session) -> list[UUID]:
    return list(session.scalars(select(RealmOutage.realm_id)))
