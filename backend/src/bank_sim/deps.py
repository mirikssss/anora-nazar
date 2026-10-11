"""Общие зависимости роутеров имитатора: контекст, песочница посетителя, ключ узла."""

import hmac
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from bank_sim.context import BankContext
from bank_sim.modules.sandboxes import service as sandboxes
from shared.errors import UnauthorizedError, ValidationFailedError

REALM_HEADER = "X-Realm-Id"
REALM_COOKIE = "realm_id"


def get_ctx(request: Request) -> BankContext:
    ctx: BankContext = request.app.state.ctx
    return ctx


Ctx = Annotated[BankContext, Depends(get_ctx)]


def get_realm(request: Request, ctx: Ctx) -> UUID:
    raw = request.headers.get(REALM_HEADER) or request.cookies.get(REALM_COOKIE)
    if not raw:
        raise ValidationFailedError("missing_realm", "Сначала начните демо: нужна песочница")
    try:
        realm_id = UUID(raw)
    except ValueError as exc:
        raise ValidationFailedError("invalid_realm", "Неверный идентификатор песочницы") from exc
    with ctx.db.transaction() as session:
        sandboxes.touch(session, realm_id, ctx.clock.now())
    return realm_id


def require_node(request: Request, ctx: Ctx) -> None:
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token, ctx.env.api_key_node):
        raise UnauthorizedError("invalid_credentials", "Неверный ключ узла")


def get_node_realm(request: Request, ctx: Ctx, _: Annotated[None, Depends(require_node)]) -> UUID:
    raw = request.headers.get(REALM_HEADER, "")
    try:
        return UUID(raw)
    except ValueError as exc:
        raise ValidationFailedError("invalid_realm", "Нужен заголовок X-Realm-Id") from exc


Realm = Annotated[UUID, Depends(get_realm)]
Node = Annotated[None, Depends(require_node)]
NodeRealm = Annotated[UUID, Depends(get_node_realm)]
