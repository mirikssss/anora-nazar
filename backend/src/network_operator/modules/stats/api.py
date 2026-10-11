"""Роутер модуля: сводка оператора для страницы риск-менеджера."""

from typing import Annotated

from fastapi import APIRouter, Depends

from network_operator.deps import Ctx, Realm, require
from network_operator.modules.clients.domain import Caller
from network_operator.modules.stats import service
from network_operator.modules.stats.schemas import StatsOut

router = APIRouter(prefix="/v1/stats", tags=["Сводка"])


@router.get("", response_model=StatsOut)
def stats(ctx: Ctx, _: Annotated[Caller, Depends(require("query"))], realm: Realm) -> StatsOut:
    with ctx.db.transaction() as session:
        return service.stats(session, realm, ctx.config.quotas, ctx.clock.now())
