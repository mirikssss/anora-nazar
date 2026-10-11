"""События банка в узел: конверт, запись вместе с изменением, доставка по порядку и отметки очереди."""

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from bank_sim.modules.outbox import repository
from bank_sim.modules.outbox.models import OutboxEvent
from shared.errors import AppError

SCHEMA_VERSION = 1


def emit(
    session: Session,
    realm_id: UUID,
    *,
    source: str,
    type_: str,
    entity_type: str,
    entity_id: str,
    entity_version: int | None,
    payload: dict[str, Any],
    occurred_at: datetime,
) -> None:
    envelope = {
        "event_id": str(uuid4()),
        "source": source,
        "type": type_,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_version": entity_version,
        "occurred_at": occurred_at.isoformat(),
        "caused_by": None,
        "schema_version": SCHEMA_VERSION,
        "payload": payload,
    }
    repository.add(
        session,
        OutboxEvent(
            realm_id=realm_id,
            envelope=envelope,
            occurred_at=occurred_at,
            delivered_at=None,
            attempts=0,
            last_error=None,
        ),
    )


def watermark(
    realm_id: UUID, producer: str, pending_count: int, oldest: datetime | None, now: datetime
) -> dict[str, Any]:
    return {
        "realm_id": str(realm_id),
        "producer": producer,
        "pending_count": pending_count,
        "oldest_pending_occurred_at": None if oldest is None else oldest.isoformat(),
        "reported_at": now.isoformat(),
    }


def realms_with_pending(session: Session) -> list[UUID]:
    return repository.realms_with_pending(session)


def pending_stats(session: Session) -> dict[UUID, tuple[int, datetime]]:
    return repository.pending_stats(session)


def deliver_realm(
    session: Session, realm_id: UUID, send: Callable[[dict[str, Any]], object], limit: int, now: datetime
) -> int:
    """По порядку, до первой ошибки: следующее событие не обгоняет недоставленное."""
    delivered = 0
    for event in repository.pending(session, realm_id, limit):
        try:
            send(event.envelope)
        except AppError as exc:
            repository.mark_failed(session, event.id, exc.message)
            break
        repository.mark_delivered(session, event.id, now)
        delivered += 1
    return delivered
