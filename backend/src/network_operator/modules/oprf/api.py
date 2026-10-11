"""Роутер модуля: вычисления OPRF по ослеплённым элементам одного типа."""

from typing import Annotated

from fastapi import APIRouter, Depends

from network_operator.deps import Ctx, Realm, require
from network_operator.modules.clients.domain import Caller
from network_operator.modules.oprf import service
from network_operator.modules.oprf.schemas import EvaluationIn, EvaluationOut

router = APIRouter(prefix="/v1/oprf", tags=["OPRF"])


@router.post("/evaluations", response_model=EvaluationOut)
def evaluate(
    body: EvaluationIn, ctx: Ctx, caller: Annotated[Caller, Depends(require("oprf"))], realm: Realm
) -> EvaluationOut:
    """Ключ типа применяется к каждому элементу; квота — по числу реальных заявок кредитора (кроме права history)."""
    with ctx.db.transaction() as session:
        return service.evaluate(session, caller, realm, body, ctx.keys, ctx.config.quotas, ctx.clock.now())
