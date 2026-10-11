"""Песочницы: создание вместе с контуром узла, сброс, удаление брошенных."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from bank_sim.modules.sandboxes import repository
from bank_sim.modules.sandboxes.models import Sandbox
from shared.errors import NotFoundError


def add(session: Session, sandbox_id: UUID, now: datetime) -> None:
    repository.add(session, Sandbox(id=sandbox_id, created_at=now, last_seen_at=now))


def touch(session: Session, sandbox_id: UUID, now: datetime) -> None:
    if not repository.exists(session, sandbox_id):
        raise NotFoundError("sandbox_not_found", "Песочница не найдена или удалена по сроку — начните заново")
    repository.touch(session, sandbox_id, now)


def remove(session: Session, sandbox_id: UUID) -> None:
    repository.remove(session, sandbox_id)


def inactive(session: Session, now: datetime, ttl: timedelta) -> list[UUID]:
    return repository.seen_before(session, now - ttl)


def all_ids(session: Session) -> list[UUID]:
    return repository.all_ids(session)
