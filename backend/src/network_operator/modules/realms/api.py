"""Роутер модуля: удаление контура песочницы и демо-сбой сети для контура."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from network_operator.deps import Ctx, require
from network_operator.modules.clients.domain import Caller
from network_operator.modules.realms import service
from network_operator.modules.realms.schemas import OutageIn, OutageOut
from shared.errors import NotFoundError

router = APIRouter(tags=["Контуры"])


@router.delete("/v1/realms/{realm_id}", status_code=204)
def delete(realm_id: UUID, ctx: Ctx, _: Annotated[Caller, Depends(require("realms"))]) -> Response:
    """Сброс или удаление песочницы по сроку: все её события, результаты, подписки и журнал у оператора."""
    with ctx.db.transaction() as session:
        service.delete(session, realm_id)
    return Response(status_code=204)


@router.put("/v1/demo/realms/{realm_id}/outage", response_model=OutageOut)
def set_outage(realm_id: UUID, body: OutageIn, ctx: Ctx, _: Annotated[Caller, Depends(require("demo"))]) -> OutageOut:
    """Кнопка сбоя «сеть недоступна»: оператор отвечает 503 на запросы этого контура. Только в демо-режиме стенда."""
    if not ctx.env.demo_mode:
        raise NotFoundError("demo_disabled", "Кнопки сбоев доступны только в демо-режиме стенда")
    with ctx.db.transaction() as session:
        service.set_outage(session, realm_id, body.active, ctx.clock.now())
    return OutageOut(active=body.active)
