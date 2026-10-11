"""Роутер модуля: реестры источников песочницы."""

from fastapi import APIRouter

from bank_sim.deps import Ctx, Realm
from bank_sim.modules.sources import service
from bank_sim.modules.sources.schemas import RegistryOut, SelfBanIn

router = APIRouter(prefix="/v1/sources", tags=["Источники"])


@router.put("/self-bans", response_model=RegistryOut)
def set_self_ban(body: SelfBanIn, ctx: Ctx, realm: Realm) -> RegistryOut:
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        service.set_self_ban(session, realm, body.pinfl, body.status, now)
        return RegistryOut(
            pinfl=body.pinfl,
            self_ban=service.self_ban_status(session, realm, body.pinfl),
            bureau=service.bureau_status(session, realm, body.pinfl, now),
        )


@router.get("/registry/{pinfl}", response_model=RegistryOut)
def registry(pinfl: str, ctx: Ctx, realm: Realm) -> RegistryOut:
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        return RegistryOut(
            pinfl=pinfl,
            self_ban=service.self_ban_status(session, realm, pinfl),
            bureau=service.bureau_status(session, realm, pinfl, now),
        )
