"""Доступ к таблицам модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from bank_sim.modules.outbox.models import OutboxEvent


def add(session: Session, event: OutboxEvent) -> None:
    session.add(event)


def pending(session: Session, realm_id: UUID, limit: int) -> list[OutboxEvent]:
    return list(
        session.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.realm_id == realm_id, OutboxEvent.delivered_at.is_(None))
            .order_by(OutboxEvent.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )


def realms_with_pending(session: Session) -> list[UUID]:
    return list(session.scalars(select(OutboxEvent.realm_id).where(OutboxEvent.delivered_at.is_(None)).distinct()))


def pending_stats(session: Session) -> dict[UUID, tuple[int, datetime]]:
    rows = session.execute(
        select(OutboxEvent.realm_id, func.count(), func.min(OutboxEvent.occurred_at))
        .where(OutboxEvent.delivered_at.is_(None))
        .group_by(OutboxEvent.realm_id)
    )
    return {realm: (count, oldest) for realm, count, oldest in rows}


def mark_delivered(session: Session, event_id: int, now: datetime) -> None:
    session.execute(update(OutboxEvent).where(OutboxEvent.id == event_id).values(delivered_at=now))


def mark_failed(session: Session, event_id: int, error: str) -> None:
    session.execute(
        update(OutboxEvent)
        .where(OutboxEvent.id == event_id)
        .values(attempts=OutboxEvent.attempts + 1, last_error=error[:512])
    )
