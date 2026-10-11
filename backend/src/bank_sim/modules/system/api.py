"""Роутер модуля: здоровье имитатора банка."""

from fastapi import APIRouter

from bank_sim.deps import Ctx
from bank_sim.modules.system import service

router = APIRouter(prefix="/v1/system", tags=["Система"])


@router.get("/health")
def health(ctx: Ctx) -> dict[str, str | None]:
    """version — коммит сборки образа; null — сборка без версии (стенд разработки)."""
    with ctx.db.transaction() as session:
        service.database_alive(session)
    return {"status": "ok", "version": ctx.env.app_version or None, "config": ctx.config.version}
