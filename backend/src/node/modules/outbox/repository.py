"""Доступ к таблицам модуля."""

from datetime import datetime
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from node.modules.outbox.models import OutboxMessage


def insert_many(session: Session, rows: list[dict[str, Any]]) -> None:
    if rows:
        session.execute(insert(OutboxMessage), rows)


def pending(session: Session, subscriber: str, limit: int) -> list[OutboxMessage]:
    return list(
        session.scalars(
            select(OutboxMessage)
            .where(OutboxMessage.subscriber == subscriber, OutboxMessage.delivered_at.is_(None))
            .order_by(OutboxMessage.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )


def mark_delivered(session: Session, ids: list[int], now: datetime) -> None:
    session.execute(update(OutboxMessage).where(OutboxMessage.id.in_(ids)).values(delivered_at=now))


def mark_failed(session: Session, ids: list[int], error: str) -> None:
    session.execute(
        update(OutboxMessage)
        .where(OutboxMessage.id.in_(ids))
        .values(attempts=OutboxMessage.attempts + 1, last_error=error[:512])
    )
