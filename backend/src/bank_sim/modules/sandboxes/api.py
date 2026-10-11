"""Роутер модуля: начать демо в своей песочнице и сбросить её."""

from uuid import uuid4

from fastapi import APIRouter, Response

from bank_sim.deps import REALM_COOKIE, Ctx, Realm
from bank_sim.modules.outbox import service as outbox
from bank_sim.modules.sandboxes import service
from bank_sim.modules.sandboxes.schemas import SandboxOut

router = APIRouter(prefix="/v1/sandboxes", tags=["Песочница"])


@router.post("", response_model=SandboxOut, status_code=201)
def create(ctx: Ctx, response: Response) -> SandboxOut:
    """Песочница появляется сначала в узле, потом здесь; первая отметка очереди уходит сразу."""
    sandbox_id = uuid4()
    ctx.node.create_realm(sandbox_id)
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        service.add(session, sandbox_id, now)
    ctx.node.send_watermarks([outbox.watermark(sandbox_id, ctx.config.producer, 0, None, now)])
    response.set_cookie(
        REALM_COOKIE, str(sandbox_id), httponly=True, samesite="lax", max_age=ctx.config.sandboxes.ttl_hours * 3600
    )
    return SandboxOut(realm_id=sandbox_id)


@router.delete("/current", status_code=204)
def reset(ctx: Ctx, realm: Realm, response: Response) -> Response:
    ctx.node.delete_realm(realm)
    with ctx.db.transaction() as session:
        service.remove(session, realm)
    response.delete_cookie(REALM_COOKIE)
    response.status_code = 204
    return response
