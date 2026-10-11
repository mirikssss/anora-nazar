"""Роутер модуля: валидация, права, вызов сервиса."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from node.deps import Ctx, require_scope
from node.modules.identity.domain import SystemPrincipal
from node.modules.realms import service
from node.modules.realms.schemas import RealmOut, SandboxCreate

router = APIRouter(prefix="/v1/realms", tags=["Песочницы"])
RealmsManager = Annotated[SystemPrincipal, Depends(require_scope("realms"))]


@router.post("", response_model=RealmOut, status_code=201)
def create_sandbox(body: SandboxCreate, ctx: Ctx, _: RealmsManager) -> RealmOut:
    with ctx.db.transaction() as session:
        realm = service.create_sandbox(session, body.id, ctx.clock.now())
    return RealmOut(id=realm.id, is_sandbox=realm.is_sandbox, world_id=realm.world_id)


@router.delete("/{realm_id}", status_code=204)
def delete_sandbox(realm_id: UUID, ctx: Ctx, _: RealmsManager) -> Response:
    with ctx.db.transaction() as session:
        service.delete_sandbox(session, realm_id)
    return Response(status_code=204)
