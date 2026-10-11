"""Роутер модуля: пакет истории синтетического мира от прогона банка."""

from typing import Annotated

from fastapi import APIRouter, Depends

from node.deps import Ctx, require_scope
from node.modules.history import service
from node.modules.history.schemas import HistoryBatchIn, HistoryBatchOut
from node.modules.identity.domain import SystemPrincipal

router = APIRouter(prefix="/v1/history", tags=["История мира"])
Replayer = Annotated[SystemPrincipal, Depends(require_scope("history"))]


@router.post("/batches", response_model=HistoryBatchOut)
def receive_batch(body: HistoryBatchIn, ctx: Ctx, _: Replayer) -> HistoryBatchOut:
    outcomes = service.run(ctx, body.items)
    return HistoryBatchOut(processed=sum(outcomes.values()), outcomes=dict(outcomes))
