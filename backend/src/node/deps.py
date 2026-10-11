"""Общие зависимости роутеров узла: контекст, кто вызывает, в каком контуре."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from node.context import NodeContext
from node.modules.identity import service as identity
from node.modules.identity.domain import Principal, StaffPrincipal, SystemPrincipal
from node.modules.realms import service as realms
from node.modules.realms.domain import RealmContext
from shared.errors import ForbiddenError, UnauthorizedError, ValidationFailedError

REALM_HEADER = "X-Realm-Id"
IDEMPOTENCY_HEADER = "Idempotency-Key"
MAX_IDEMPOTENCY_KEY = 128


def get_ctx(request: Request) -> NodeContext:
    ctx: NodeContext = request.app.state.ctx
    return ctx


Ctx = Annotated[NodeContext, Depends(get_ctx)]


def get_principal(request: Request, ctx: Ctx) -> Principal:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise UnauthorizedError("missing_credentials", "Нужен ключ системы или токен сотрудника")
    with ctx.db.transaction() as session:
        return identity.authenticate(session, header.removeprefix("Bearer ").strip(), ctx.env.session_secret)


def _parse_realm(raw: str | None) -> UUID:
    if not raw:
        raise ValidationFailedError("missing_realm", f"Нужен заголовок {REALM_HEADER}")
    try:
        return UUID(raw)
    except ValueError as exc:
        raise ValidationFailedError("invalid_realm", "Неверный идентификатор песочницы") from exc


def _resolve(ctx: NodeContext, realm_id: UUID) -> RealmContext:
    with ctx.db.transaction() as session:
        return realms.resolve(session, realm_id, ctx.clock.now())


def get_public_realm(request: Request, ctx: Ctx) -> RealmContext:
    return _resolve(ctx, _parse_realm(request.headers.get(REALM_HEADER)))


def get_realm(request: Request, ctx: Ctx, principal: Annotated[Principal, Depends(get_principal)]) -> RealmContext:
    header = request.headers.get(REALM_HEADER)
    if isinstance(principal, StaffPrincipal):
        if header and _parse_realm(header) != principal.realm_id:
            raise ForbiddenError("realm_mismatch", "Токен выдан для другой песочницы")
        return _resolve(ctx, principal.realm_id)
    return _resolve(ctx, _parse_realm(header))


def get_idempotency_key(request: Request) -> str:
    key = request.headers.get(IDEMPOTENCY_HEADER, "").strip()
    if not key or len(key) > MAX_IDEMPOTENCY_KEY:
        raise ValidationFailedError(
            "missing_idempotency_key", f"Нужен заголовок {IDEMPOTENCY_HEADER} длиной до {MAX_IDEMPOTENCY_KEY} символов"
        )
    return key


IdempotencyKey = Annotated[str, Depends(get_idempotency_key)]
Realm = Annotated[RealmContext, Depends(get_realm)]
PublicRealm = Annotated[RealmContext, Depends(get_public_realm)]


def require_scope(scope: str) -> Callable[..., SystemPrincipal]:
    def dependency(principal: Annotated[Principal, Depends(get_principal)]) -> SystemPrincipal:
        if not isinstance(principal, SystemPrincipal) or scope not in principal.scopes:
            raise ForbiddenError("scope_required", f"Нужно право системы «{scope}»")
        return principal

    return dependency


def require_permission(permission: str) -> Callable[..., StaffPrincipal]:
    def dependency(principal: Annotated[Principal, Depends(get_principal)]) -> StaffPrincipal:
        if not isinstance(principal, StaffPrincipal) or permission not in principal.permissions:
            raise ForbiddenError("permission_required", f"Нужно право «{permission}»")
        return principal

    return dependency
