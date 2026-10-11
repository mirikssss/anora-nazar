"""Роутер модуля: счётчики совпадений по токенам заявок."""

from typing import Annotated

from fastapi import APIRouter, Depends

from network_operator.deps import Ctx, Realm, require
from network_operator.modules.clients.domain import Caller
from network_operator.modules.counters import service
from network_operator.modules.counters.schemas import CountersIn, CountersOut

router = APIRouter(prefix="/v1/counters", tags=["Счётчики"])


@router.post("/queries", response_model=CountersOut)
def query(
    body: CountersIn, ctx: Ctx, caller: Annotated[Caller, Depends(require("query"))], realm: Realm
) -> CountersOut:
    """Только числа и совпадения с закрытыми делами, без имён других кредиторов; as_of — только с правом history."""
    can_watch = caller.lender is not None and ctx.callbacks.can_notify(caller.lender)
    with ctx.db.transaction() as session:
        return service.query(session, caller, realm, body, ctx.config, ctx.clock.now(), can_watch=can_watch)
