"""Общие зависимости роутеров оператора: контекст, кто вызывает, в каком контуре.

Контур — заголовок X-Realm-Id (песочница); без заголовка — общий мир. Контур с демо-сбоем получает 503.
"""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from network_operator.context import OperatorContext
from network_operator.modules.clients import service as clients
from network_operator.modules.clients.domain import Caller
from network_operator.modules.realms import service as realms
from shared.errors import UnauthorizedError, ValidationFailedError

REALM_HEADER = "X-Realm-Id"


def get_ctx(request: Request) -> OperatorContext:
    ctx: OperatorContext = request.app.state.ctx
    return ctx


Ctx = Annotated[OperatorContext, Depends(get_ctx)]


def get_caller(request: Request, ctx: Ctx) -> Caller:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise UnauthorizedError("missing_credentials", "Нужен ключ кредитора")
    with ctx.db.transaction() as session:
        return clients.authenticate(session, header.removeprefix("Bearer ").strip())


def get_realm(request: Request, ctx: Ctx) -> UUID | None:
    raw = request.headers.get(REALM_HEADER)
    if not raw:
        return None
    try:
        realm_id = UUID(raw)
    except ValueError as exc:
        raise ValidationFailedError("invalid_realm", "Неверный идентификатор песочницы") from exc
    with ctx.db.transaction() as session:
        realms.ensure_available(session, realm_id)
    return realm_id


def require(scope: str) -> Callable[..., Caller]:
    def dependency(caller: Annotated[Caller, Depends(get_caller)]) -> Caller:
        clients.require(caller, scope)
        return caller

    return dependency


Realm = Annotated[UUID | None, Depends(get_realm)]
