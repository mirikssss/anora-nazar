"""Сессионный антифрод приложения: события сессии уходят в узел как факты источника."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from bank_sim.modules.outbox import service as outbox

SOURCE = "bank-sim.sessions"


def report(
    session: Session, realm_id: UUID, *, pinfl: str, event_type: str, device_id: str | None, occurred_at: datetime
) -> str:
    session_event_id = str(uuid4())
    outbox.emit(
        session,
        realm_id,
        source=SOURCE,
        type_=f"session.{event_type}",
        entity_type="session_event",
        entity_id=session_event_id,
        entity_version=None,
        payload={"subject_pinfl": pinfl, "device_id": device_id},
        occurred_at=occurred_at,
    )
    return session_event_id
