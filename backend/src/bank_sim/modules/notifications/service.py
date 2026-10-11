"""Уведомления узла: принимаются один раз, пометка «нужна новая оценка» отражается на заявке конвейера."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from bank_sim.modules.conveyor import service as conveyor
from bank_sim.modules.notifications import repository
from bank_sim.modules.notifications.models import NodeNotification
from bank_sim.modules.notifications.schemas import NotificationIn
from bank_sim.modules.sandboxes import service as sandboxes

REASSESSMENT_REQUIRED = "application.reassessment_required"


def accept(session: Session, messages: list[NotificationIn], now: datetime) -> int:
    alive = set(sandboxes.all_ids(session))
    accepted = 0
    for message in messages:
        if message.realm_id not in alive:
            continue
        if repository.add_if_new(
            session,
            {
                "message_id": message.id,
                "realm_id": message.realm_id,
                "topic": message.topic,
                "payload": message.payload,
                "received_at": now,
            },
        ):
            accepted += 1
            if message.topic == REASSESSMENT_REQUIRED:
                conveyor.note_reassessment_required(
                    session, message.realm_id, str(message.payload["application_id"]), now
                )
    return accepted


def recent(session: Session, realm_id: UUID, limit: int) -> list[NodeNotification]:
    return repository.recent(session, realm_id, limit)


def for_application(session: Session, realm_id: UUID, application_id: str) -> list[NodeNotification]:
    """Уведомления узла по одной заявке в порядке его outbox."""
    return repository.for_application(session, realm_id, application_id)
