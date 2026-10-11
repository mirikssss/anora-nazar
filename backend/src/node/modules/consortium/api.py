"""Роутер модуля: уведомления оператора сети и обзор сети для риск-менеджера."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from node.deps import REALM_HEADER, Ctx, Realm, parse_realm, require_permission, require_scope
from node.modules.consortium import service
from node.modules.consortium.schemas import NetworkOverviewOut, NotificationOut
from node.modules.decisions import service as decisions
from node.modules.identity.domain import StaffPrincipal, SystemPrincipal
from node.modules.realms import service as realms
from shared.contracts.network import MatchNotification

router = APIRouter(prefix="/v1/network", tags=["Сеть кредиторов"])
Operator = Annotated[SystemPrincipal, Depends(require_scope("network"))]
Viewer = Annotated[StaffPrincipal, Depends(require_permission("quality.view"))]


@router.post("/notifications", response_model=NotificationOut)
def receive_notification(body: MatchNotification, request: Request, ctx: Ctx, _: Operator) -> NotificationOut:
    """Оператор шлёт уведомление в контур песочницы с заголовком, в общий мир — без него."""
    header = request.headers.get(REALM_HEADER)
    with ctx.db.transaction() as session:
        now = ctx.clock.now()
        realm_id = realms.world_id(session) if not header else parse_realm(header)
        realm = realms.resolve(session, realm_id, now)
        return NotificationOut(outcome=service.on_notification(session, ctx.network(), realm, body, now))


@router.get("/overview", response_model=NetworkOverviewOut)
def overview(ctx: Ctx, realm: Realm, _: Viewer) -> NetworkOverviewOut:
    with ctx.db.transaction() as session:
        bundle = ctx.policies.for_realm(session, realm)
        counts = decisions.network_status_counts(session, realm.id)
        return NetworkOverviewOut.model_validate(service.overview(session, ctx.network(), realm, bundle.policy, counts))
