"""Роутер модуля: здоровье якоря."""

from fastapi import APIRouter, Request

from anchor.context import AnchorContext
from anchor.modules.system import service

router = APIRouter(prefix="/v1/system", tags=["Система"])


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    ctx: AnchorContext = request.app.state.ctx
    with ctx.db.transaction() as session:
        service.database_alive(session)
    return {"status": "ok"}
