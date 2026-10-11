"""Роутер модуля: здоровье и метрики."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from node.deps import Ctx, Realm, require_permission
from node.modules.identity.domain import StaffPrincipal
from node.modules.system import service

router = APIRouter(prefix="/v1/system", tags=["Система"])


@router.get("/health")
def health(ctx: Ctx) -> dict[str, str | None]:
    """version — коммит сборки образа; null — сборка без версии (стенд разработки)."""
    with ctx.db.transaction() as session:
        service.database_alive(session)
    return {
        "status": "ok",
        "version": ctx.env.app_version or None,
        "policy": ctx.policies.active_version,
        "config": ctx.config.version,
    }


@router.get("/metrics")
def metrics(
    ctx: Ctx, realm: Realm, _: Annotated[StaffPrincipal, Depends(require_permission("audit.view"))]
) -> dict[str, Any]:
    with ctx.db.transaction() as session:
        return service.metrics(session, realm.id)
