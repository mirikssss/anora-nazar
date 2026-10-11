"""Доступ к таблицам модуля."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from anchor.modules.checkpoints.models import Checkpoint


def get(session: Session, realm_id: UUID, seq: int) -> Checkpoint | None:
    return session.get(Checkpoint, (realm_id, seq))


def add(session: Session, checkpoint: Checkpoint) -> None:
    session.add(checkpoint)


def for_realm(session: Session, realm_id: UUID) -> list[Checkpoint]:
    return list(session.scalars(select(Checkpoint).where(Checkpoint.realm_id == realm_id).order_by(Checkpoint.seq)))
