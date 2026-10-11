"""Роутер модуля: приём уведомлений узла и лента песочницы."""

from typing import Annotated

from fastapi import APIRouter, Query

from bank_sim.deps import Ctx, Node, Realm
from bank_sim.modules.notifications import service
from bank_sim.modules.notifications.schemas import NotificationOut, NotificationsIn

router = APIRouter(tags=["Уведомления узла"])
MAX_FEED = 200


@router.post("/v1/node/notifications")
def accept(body: NotificationsIn, ctx: Ctx, _: Node) -> dict[str, int]:
    with ctx.db.transaction() as session:
        return {"accepted": service.accept(session, body.messages, ctx.clock.now())}


@router.get("/v1/notifications", response_model=list[NotificationOut])
def feed(ctx: Ctx, realm: Realm, limit: Annotated[int, Query(ge=1, le=MAX_FEED)] = 50) -> list[NotificationOut]:
    with ctx.db.transaction() as session:
        return [
            NotificationOut(message_id=n.message_id, topic=n.topic, payload=n.payload, received_at=n.received_at)
            for n in service.recent(session, realm, limit)
        ]
