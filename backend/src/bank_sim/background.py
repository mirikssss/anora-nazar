"""Фоновые задачи имитатора: доставка событий в узел, отметки очереди, удаление брошенных песочниц."""

import logging
from datetime import datetime, timedelta
from functools import partial
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from bank_sim.context import BankContext
from bank_sim.modules.failures import service as failures
from bank_sim.modules.outbox import service as outbox
from bank_sim.modules.sandboxes import service as sandboxes
from shared.background import LeaderLoop, Task
from shared.errors import AppError

log = logging.getLogger(__name__)
LEADER_LOCK = 0x42414E4B  # «BANK»


class BankTasks:
    def __init__(self, ctx: BankContext) -> None:
        self._ctx = ctx
        self._last_watermark: datetime | None = None

    def loop(self) -> LeaderLoop:
        tasks: list[Task] = [
            ("deliver_events", self.deliver_events),
            ("report_watermarks", self.report_watermarks),
            ("delete_inactive_sandboxes", self.delete_inactive_sandboxes),
        ]
        return LeaderLoop(self._ctx.db, LEADER_LOCK, self._ctx.config.background.tick_seconds, tasks, "bank-background")

    def deliver_events(self) -> None:
        """Очередь песочницы стоит, если включён сбой «очередь отстаёт» или «узел недоступен»."""
        with self._ctx.db.transaction() as session:
            realms = [r for r in outbox.realms_with_pending(session) if self._can_deliver(session, r)]
        for realm_id in realms:
            with self._ctx.db.transaction() as session:
                outbox.deliver_realm(
                    session,
                    realm_id,
                    partial(self._ctx.node.send_event, realm_id),
                    self._ctx.config.outbox.batch_size,
                    self._ctx.clock.now(),
                )

    @staticmethod
    def _can_deliver(session: Session, realm_id: UUID) -> bool:
        return not failures.delivery_held(failures.flags(session, realm_id))

    def report_watermarks(self) -> None:
        now = self._ctx.clock.now()
        interval = timedelta(seconds=self._ctx.config.background.watermark_interval_seconds)
        if self._last_watermark is not None and now - self._last_watermark < interval:
            return
        with self._ctx.db.transaction() as session:
            stats = outbox.pending_stats(session)
            realms = [r for r in sandboxes.all_ids(session) if not failures.flags(session, r).node_unavailable]
        items = [self._watermark(r, stats, now) for r in realms]
        if not items:
            return
        try:
            self._ctx.node.send_watermarks(items)
        except AppError as exc:
            log.warning("отметки очереди не доставлены: %s", exc.message)
            return
        self._last_watermark = now

    def _watermark(self, realm_id: UUID, stats: dict[UUID, tuple[int, datetime]], now: datetime) -> dict[str, Any]:
        count, oldest = stats.get(realm_id, (0, None))
        return outbox.watermark(realm_id, self._ctx.config.producer, count, oldest, now)

    def delete_inactive_sandboxes(self) -> None:
        ttl = timedelta(hours=self._ctx.config.sandboxes.ttl_hours)
        with self._ctx.db.transaction() as session:
            for realm_id in sandboxes.inactive(session, self._ctx.clock.now(), ttl):
                sandboxes.remove(session, realm_id)
