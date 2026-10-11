"""Роутер модуля: роли имитатора банка для страницы входа."""

from fastapi import APIRouter

from bank_sim.deps import Ctx
from bank_sim.modules.personas import service
from bank_sim.modules.personas.schemas import BankRoleOut

router = APIRouter(prefix="/v1/roles", tags=["Роли"])


@router.get("", response_model=list[BankRoleOut])
def list_roles(ctx: Ctx) -> list[BankRoleOut]:
    with ctx.db.transaction() as session:
        return [BankRoleOut.model_validate(r) for r in service.roles(session)]
