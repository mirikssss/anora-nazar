"""Роутер модуля: здоровье имитатора банка."""

from fastapi import APIRouter

from bank_sim.deps import Ctx
from bank_sim.modules.system import service

router = APIRouter(prefix="/v1/system", tags=["Система"])


@router.get("/health")
def health(ctx: Ctx) -> dict[str, str]:
    with ctx.db.transaction() as session:
        service.database_alive(session)
    return {"status": "ok", "config": ctx.config.version}
