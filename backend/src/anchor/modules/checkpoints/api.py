"""Роутер модуля: приём и выдача контрольных точек. Пишет и читает только узел по своему ключу."""

import hmac
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from anchor.context import AnchorContext
from anchor.modules.checkpoints import service
from anchor.modules.checkpoints.schemas import CheckpointIn, CheckpointOut, CheckpointsOut
from shared.errors import UnauthorizedError

router = APIRouter(prefix="/v1/checkpoints", tags=["Контрольные точки"])


def get_ctx(request: Request) -> AnchorContext:
    ctx: AnchorContext = request.app.state.ctx
    return ctx


def require_node(request: Request, ctx: Annotated[AnchorContext, Depends(get_ctx)]) -> None:
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, ctx.env.api_key_node):
        raise UnauthorizedError("invalid_credentials", "Неверный ключ узла")


Ctx = Annotated[AnchorContext, Depends(get_ctx)]
Node = Annotated[None, Depends(require_node)]


def _out(c: object) -> CheckpointOut:
    return CheckpointOut.model_validate(c, from_attributes=True)


@router.post("", response_model=CheckpointOut, status_code=201)
def accept(body: CheckpointIn, ctx: Ctx, _: Node) -> CheckpointOut:
    with ctx.db.transaction() as session:
        return _out(service.accept(session, body, ctx.verifier, ctx.clock.now()))


@router.get("", response_model=CheckpointsOut)
def list_checkpoints(ctx: Ctx, _: Node, realm_id: Annotated[UUID, Query()]) -> CheckpointsOut:
    with ctx.db.transaction() as session:
        return CheckpointsOut(items=[_out(c) for c in service.list_for_realm(session, realm_id)])
