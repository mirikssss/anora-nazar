"""Доступ к таблицам модуля."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from bank_sim.modules.notifications.models import NodeNotification


def add_if_new(session: Session, values: dict[str, Any]) -> bool:
    stmt = insert(NodeNotification).values(**values).on_conflict_do_nothing().returning(NodeNotification.message_id)
    return session.scalar(stmt) is not None


def recent(session: Session, realm_id: UUID, limit: int) -> list[NodeNotification]:
    return list(
        session.scalars(
            select(NodeNotification)
            .where(NodeNotification.realm_id == realm_id)
            .order_by(NodeNotification.message_id.desc())
            .limit(limit)
        )
    )
