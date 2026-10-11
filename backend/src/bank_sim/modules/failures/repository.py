"""Доступ к таблицам модуля."""

from uuid import UUID

from sqlalchemy.orm import Session

from bank_sim.modules.failures.models import FailureFlags


def get(session: Session, realm_id: UUID) -> FailureFlags | None:
    return session.get(FailureFlags, realm_id)


def add(session: Session, flags: FailureFlags) -> None:
    session.add(flags)
