"""Фоновые задачи оператора: доставка уведомлений кредиторам и снятие подписок по сроку."""

import logging

from network_operator.callbacks import DeliveryError
from network_operator.context import OperatorContext
from network_operator.modules.realms import service as realms
from network_operator.modules.watches import service as watches
from shared.background import LeaderLoop, Task
from shared.contracts.network import MatchNotification

log = logging.getLogger(__name__)
LEADER_LOCK = 0x4E455457  # «NETW»


class OperatorTasks:
    def __init__(self, ctx: OperatorContext) -> None:
        self._ctx = ctx

    def loop(self) -> LeaderLoop:
        tasks: list[Task] = [
            ("deliver_notifications", self.deliver_notifications),
            ("expire_watches", self.expire_watches),
        ]
        tick = self._ctx.config.notifications.tick_seconds
        return LeaderLoop(self._ctx.db, LEADER_LOCK, tick, tasks, "operator-background")

    def deliver_notifications(self) -> None:
        """HTTP — вне транзакции; итог каждой доставки — своей транзакцией. Контуры с демо-сбоем ждут."""
        config = self._ctx.config.notifications
        with self._ctx.db.transaction() as session:
            pending = watches.due(session, self._ctx.clock.now(), config.batch_size, realms.outages(session))
        for item in pending:
            notification = MatchNotification.model_validate(
                {"notification_id": str(item.id), "ref": item.ref, "kinds": item.kinds, "occurred_at": item.occurred_at}
            )
            try:
                self._ctx.callbacks.send(item.lender, item.realm_id, notification)
            except DeliveryError as exc:
                log.warning("уведомление %s не доставлено: %s", item.id, exc)
                with self._ctx.db.transaction() as session:
                    watches.failed_attempt(session, item, str(exc), self._ctx.clock.now(), config)
                continue
            with self._ctx.db.transaction() as session:
                watches.delivered(session, item, self._ctx.clock.now())

    def expire_watches(self) -> None:
        with self._ctx.db.transaction() as session:
            watches.delete_expired(session, self._ctx.clock.now())
