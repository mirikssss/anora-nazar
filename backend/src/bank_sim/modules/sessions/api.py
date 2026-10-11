"""Роутер модуля: событие сессии приложения."""

from fastapi import APIRouter

from bank_sim.deps import Ctx, Realm
from bank_sim.modules.sessions import service
from bank_sim.modules.sessions.schemas import SessionEventIn, SessionEventOut

router = APIRouter(prefix="/v1/sessions", tags=["Сессии приложения"])


@router.post("/events", response_model=SessionEventOut, status_code=201)
def report(body: SessionEventIn, ctx: Ctx, realm: Realm) -> SessionEventOut:
    with ctx.db.transaction() as session:
        event_id = service.report(
            session,
            realm,
            pinfl=body.pinfl,
            event_type=body.event_type,
            device_id=body.device_id,
            occurred_at=ctx.clock.now(),
        )
    return SessionEventOut(session_event_id=event_id)
