"""Доступ к таблицам модуля."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from node.modules.decisions.models import Decision


def add(session: Session, decision: Decision) -> None:
    session.add(decision)


def get_visible(session: Session, realm_ids: tuple[UUID, ...], decision_id: UUID) -> Decision | None:
    return session.scalars(
        select(Decision).where(Decision.id == decision_id, Decision.realm_id.in_(realm_ids))
    ).one_or_none()
