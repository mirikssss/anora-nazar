"""Роутер модуля: здоровье оператора."""

from fastapi import APIRouter

from network_operator.deps import Ctx
from network_operator.modules.system import service

router = APIRouter(prefix="/v1/system", tags=["Система"])


@router.get("/health")
def health(ctx: Ctx) -> dict[str, str | None]:
    """version — коммит сборки образа; null — сборка без версии (стенд разработки)."""
    with ctx.db.transaction() as session:
        service.database_alive(session)
    return {"status": "ok", "version": ctx.env.app_version or None}
