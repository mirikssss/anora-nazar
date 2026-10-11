"""События банка в узел: конверт, запись вместе с изменением, доставка по порядку и отметки очереди."""

from collections.abc import Callable
from datetime import datetime
from functools import partial
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from bank_sim.context import BankContext
from bank_sim.modules.failures import service as failures
from bank_sim.modules.outbox import repository
from bank_sim.modules.outbox.models import OutboxEvent
from shared.errors import AppError

Send = Callable[[dict[str, Any]], object]

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


def _deliver(session: Session, events: list[OutboxEvent], send: Send, now: datetime) -> int:
    """По порядку, до первой ошибки: следующее событие не обгоняет недоставленное."""
    delivered = 0
    for event in events:
        try:
            send(event.envelope)
        except AppError as exc:
            repository.mark_failed(session, event.id, exc.message)
            break
        repository.mark_delivered(session, event.id, now)
        delivered += 1
    return delivered


def deliver_realm(session: Session, realm_id: UUID, send: Send, limit: int, now: datetime) -> int:
    """Фоновая доставка. Голову очереди сейчас отправляет flush_realm — такт пропускает песочницу, а не обгоняет."""
    batch = repository.pending(session, realm_id, limit)
    if not batch or batch[0].id != repository.first_pending_id(session, realm_id):
        return 0
    return _deliver(session, batch, send, now)


def flush_realm(ctx: BankContext, realm_id: UUID) -> bool:
    """Доставляет очередь песочницы сразу, не дожидаясь фонового такта: факты источников и ответы клиента доходят
    до узла раньше оценки и раньше следующего экрана. Сбои «очередь отстаёт» и «узел недоступен» держат очередь,
    как и в фоне; недоставленное уйдёт фоном. True — очередь песочницы пуста."""
    with ctx.db.transaction() as session:
        if failures.delivery_held(failures.flags(session, realm_id)):
            return False
    send = partial(ctx.node.send_event, realm_id)
    while True:
        with ctx.db.transaction() as session:
            batch = repository.pending(session, realm_id, ctx.config.outbox.batch_size, wait=True)
            if not batch:
                return True
            if _deliver(session, batch, send, ctx.clock.now()) < len(batch):
                return False
