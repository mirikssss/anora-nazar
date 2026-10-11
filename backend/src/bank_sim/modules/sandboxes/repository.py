"""Доступ к таблицам модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from bank_sim.modules.sandboxes.models import Sandbox


def add(session: Session, sandbox: Sandbox) -> None:
    session.add(sandbox)


def exists(session: Session, sandbox_id: UUID) -> bool:
    return session.get(Sandbox, sandbox_id) is not None


def touch(session: Session, sandbox_id: UUID, now: datetime) -> None:
    session.execute(update(Sandbox).where(Sandbox.id == sandbox_id).values(last_seen_at=now))


def remove(session: Session, sandbox_id: UUID) -> None:
    session.execute(delete(Sandbox).where(Sandbox.id == sandbox_id))


def seen_before(session: Session, moment: datetime) -> list[UUID]:
    return list(session.scalars(select(Sandbox.id).where(Sandbox.last_seen_at < moment)))


def all_ids(session: Session) -> list[UUID]:
    return list(session.scalars(select(Sandbox.id)))
