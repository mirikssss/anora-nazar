"""Роутер модуля: приём событий активности кредитора."""

from typing import Annotated

from fastapi import APIRouter, Depends

from network_operator.deps import Ctx, Realm, require
from network_operator.modules.activity import service
from network_operator.modules.activity.schemas import ActivityIn, ActivityOut
from network_operator.modules.clients.domain import Caller

router = APIRouter(prefix="/v1/activity", tags=["События активности"])


@router.post("/events", response_model=ActivityOut)
def ingest(
    body: ActivityIn, ctx: Ctx, caller: Annotated[Caller, Depends(require("activity"))], realm: Realm
) -> ActivityOut:
    """Дубли и конфликты не меняют событие; исправление и отмена действуют с момента получения оператором."""
    return ctx.db.run(lambda session: service.ingest(session, caller, realm, body, ctx.clock.now()))
