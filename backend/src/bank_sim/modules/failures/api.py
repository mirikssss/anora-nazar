"""Роутер модуля: кнопки сбоев песочницы."""

from fastapi import APIRouter

from bank_sim.deps import Ctx, Realm
from bank_sim.modules.core_banking import service as core_banking
from bank_sim.modules.failures import service
from bank_sim.modules.failures.schemas import Flags, FlagsPatch, RepeatIn, RepeatOut

router = APIRouter(prefix="/v1/failures", tags=["Сбои"])


@router.get("", response_model=Flags)
def get_flags(ctx: Ctx, realm: Realm) -> Flags:
    with ctx.db.transaction() as session:
        return service.flags(session, realm)


@router.patch("", response_model=Flags)
def set_flags(body: FlagsPatch, ctx: Ctx, realm: Realm) -> Flags:
    with ctx.db.transaction() as session:
        return service.update(session, realm, body, ctx.clock.now())


@router.post("/repeat-with-other-amount", response_model=RepeatOut)
def repeat_with_other_amount(body: RepeatIn, ctx: Ctx, realm: Realm) -> RepeatOut:
    response = core_banking.repeat_with_other_amount(ctx, realm, body.operation_key, body.amount)
    return RepeatOut(node_status_code=response.status_code, node_response=response.json())
