"""Сессионный антифрод приложения: события сессии уходят в узел как факты источника."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from bank_sim.modules.outbox import service as outbox
from bank_sim.modules.sessions.domain import SessionProfile, session_summary

SOURCE = "bank-sim.sessions"
SUMMARY = "session.summary"
SUMMARY_ENTITY = "session"


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


def report_summary(
    session: Session,
    realm_id: UUID,
    *,
    pinfl: str,
    application_id: str,
    device_id: str,
    profile: SessionProfile,
    now: datetime,
) -> None:
    """Сводка сессии заявки — факт для узла; уходит до оценки, как в банке перед вызовом Т1."""
    outbox.emit(
        session,
        realm_id,
        source=SOURCE,
        type_=SUMMARY,
        entity_type=SUMMARY_ENTITY,
        entity_id=application_id,
        entity_version=None,
        payload=session_summary(pinfl, application_id, device_id, profile, now).model_dump(mode="json"),
        occurred_at=now,
    )
