"""Транзакционный outbox: запись вместе с состоянием, доставка подписчикам отдельно и с повтором."""

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from node.modules.outbox import repository
from node.settings import OutboxConfig
from shared.errors import AppError


def enqueue(
    session: Session, config: OutboxConfig, realm_id: UUID, topic: str, payload: dict[str, Any], now: datetime
) -> None:
    repository.insert_many(
        session,
        [
            {
                "realm_id": realm_id,
                "subscriber": s.name,
                "topic": topic,
                "payload": payload,
                "created_at": now,
                "delivered_at": None,
                "attempts": 0,
                "last_error": None,
            }
            for s in config.subscribers
            if topic in s.topics
        ],
    )


Deliver = Callable[[list[dict[str, Any]]], object]


def deliver_pending(session: Session, config: OutboxConfig, senders: Mapping[str, Deliver], now: datetime) -> int:
    """Отдаёт пачку каждому подписчику. Неудача — сообщения остаются и уйдут на следующем такте."""
    delivered = 0
    for subscriber in config.subscribers:
        batch = repository.pending(session, subscriber.name, config.batch_size)
        if not batch:
            continue
        messages = [
            {
                "id": m.id,
                "realm_id": str(m.realm_id),
                "topic": m.topic,
                "payload": m.payload,
                "created_at": m.created_at.isoformat(),
            }
            for m in batch
        ]
        try:
            senders[subscriber.name](messages)
        except AppError as exc:
            repository.mark_failed(session, [m.id for m in batch], exc.message)
            continue
        repository.mark_delivered(session, [m.id for m in batch], now)
        delivered += len(batch)
    return delivered
