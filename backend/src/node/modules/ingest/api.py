"""Роутер модуля: события систем банка и отметки их очередей."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from node.deps import Ctx, Realm, require_scope
from node.modules.identity.domain import SystemPrincipal
from node.modules.ingest import service
from node.modules.ingest.schemas import EventIn, EventResult, WatermarksIn
from node.modules.realms import service as realms

router = APIRouter(prefix="/v1/events", tags=["События"])
Events = Annotated[SystemPrincipal, Depends(require_scope("events"))]


@router.post("", response_model=EventResult)
def receive(body: EventIn, ctx: Ctx, realm: Realm, _: Events) -> EventResult:
    received_at = ctx.clock.now()
    intake = ctx.intake()
    outcome = ctx.db.run(lambda session: service.receive(session, intake, realm, body, received_at))
    return EventResult(event_id=body.event_id, outcome=outcome)


@router.post("/watermarks", status_code=204)
def report_watermarks(body: WatermarksIn, ctx: Ctx, _: Events) -> Response:
    """Отметки по удалённым песочницам пропускаются: их очереди больше никого не задерживают."""
    with ctx.db.transaction() as session:
        alive = realms.existing(session, [item.realm_id for item in body.items])
        service.report_watermarks(session, [item for item in body.items if item.realm_id in alive])
    return Response(status_code=204)
