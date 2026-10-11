"""Роутер модуля: результаты закрытых дел кредитора."""

from typing import Annotated

from fastapi import APIRouter, Depends

from network_operator.deps import Ctx, Realm, require
from network_operator.modules.clients.domain import Caller
from network_operator.modules.confirmed import service
from network_operator.modules.confirmed.schemas import ConfirmedIn, ConfirmedOut

router = APIRouter(prefix="/v1/confirmed", tags=["Результаты проверок"])


@router.post("/results", response_model=ConfirmedOut)
def accept(
    body: ConfirmedIn, ctx: Ctx, caller: Annotated[Caller, Depends(require("confirmed"))], realm: Realm
) -> ConfirmedOut:
    """Только подтверждённый фрод и подтверждённое воздействие — идентификаторы мошенника, не жертвы."""
    with ctx.db.transaction() as session:
        return service.accept(session, caller, realm, body, ctx.clock.now())
