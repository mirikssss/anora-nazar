"""Роутер модуля: валидация, права, вызов сервиса."""

from typing import Annotated

from fastapi import APIRouter, Depends

from node.deps import Ctx, PublicRealm, get_principal
from node.modules.identity import service
from node.modules.identity.domain import Principal, StaffPrincipal
from node.modules.identity.schemas import DemoLoginIn, DemoLoginOut, MeOut, StaffRoleOut, StaffUserOut
from shared.errors import ForbiddenError, NotFoundError

router = APIRouter(prefix="/v1", tags=["Сотрудники и вход"])


def _me(principal: StaffPrincipal) -> MeOut:
    return MeOut(
        user_code=principal.user_code,
        role_code=principal.role_code,
        display_name=principal.display_name,
        division=principal.division,
        permissions=sorted(principal.permissions),
    )


@router.get("/staff/roles", response_model=list[StaffRoleOut])
def list_roles(ctx: Ctx) -> list[StaffRoleOut]:
    with ctx.db.transaction() as session:
        return [
            StaffRoleOut(
                code=role.code,
                title=role.title,
                home_path=role.home_path,
                summary=role.summary,
                permissions=role.permissions,
                restrictions=role.restrictions,
                users=[StaffUserOut(code=u.code, display_name=u.display_name, division=u.division) for u in users],
            )
            for role, users in service.list_roles(session)
        ]


@router.post("/auth/demo-login", response_model=DemoLoginOut)
def demo_login(body: DemoLoginIn, ctx: Ctx, realm: PublicRealm) -> DemoLoginOut:
    if not ctx.env.demo_mode:
        raise NotFoundError("demo_login_disabled", "Вход без пароля есть только на демо-стенде")
    if not realm.is_sandbox:
        raise ForbiddenError("sandbox_required", "Демо-вход — только в своей песочнице: общий мир посетители не меняют")
    with ctx.db.transaction() as session:
        token, principal = service.demo_login(session, body.user_code, realm.id, ctx.env.session_secret)
    return DemoLoginOut(token=token, me=_me(principal))


@router.get("/auth/me", response_model=MeOut)
def me(principal: Annotated[Principal, Depends(get_principal)]) -> MeOut:
    if not isinstance(principal, StaffPrincipal):
        raise ForbiddenError("staff_only", "Только для сотрудников")
    return _me(principal)
