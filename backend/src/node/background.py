"""Фоновые задачи узла: просрочка резервов и сверка, пропуски версий, outbox, контрольные точки, песочницы."""

import logging
from datetime import timedelta
from functools import partial
from uuid import UUID

from sqlalchemy.orm import Session

from node.context import NodeContext
from node.modules.applications import service as applications
from node.modules.audit import anchoring
from node.modules.audit import service as audit
from node.modules.ingest import service as ingest
from node.modules.outbox import service as outbox
from node.modules.permits import service as permits
from node.modules.realms import service as realms
from shared.background import LeaderLoop, Task
from shared.contracts.application import ApplicationSnapshot
from shared.errors import AppError

log = logging.getLogger(__name__)
LEADER_LOCK = 0x4E415A4152  # «NAZAR»: один ключ на все экземпляры узла
RECONCILE_BATCH = 50


class NodeTasks:
    """Задачи ведущего процесса узла."""

    def __init__(self, ctx: NodeContext) -> None:
        self._ctx = ctx

    def loop(self) -> LeaderLoop:
        tasks: list[Task] = [
            ("expire_reserved", self.expire_reserved),
            ("reconcile_unknown", self.reconcile_unknown),
            ("resolve_version_gaps", self.resolve_version_gaps),
            ("deliver_outbox", self.deliver_outbox),
            ("checkpoints", self.checkpoints),
            ("delete_inactive_sandboxes", self.delete_inactive_sandboxes),
        ]
        return LeaderLoop(self._ctx.db, LEADER_LOCK, self._ctx.config.background.tick_seconds, tasks, "node-background")

    def expire_reserved(self) -> None:
        now = self._ctx.clock.now()
        with self._ctx.db.transaction() as session:
            permits.expire_reserved(session, now)

    def reconcile_unknown(self) -> None:
        with self._ctx.db.transaction() as session:
            candidates = permits.unknown_operations(session, RECONCILE_BATCH)
        for realm_id, key in candidates:
            try:
                body = self._ctx.bank.call("GET", f"/v1/node/operations/{key}", realm_id=realm_id)
            except AppError as exc:
                if exc.status_code != 404:
                    continue
                body = {"status": "not_found"}
            status = str(body["status"])
            if status == "in_progress":
                continue
            with self._ctx.db.transaction() as session:
                permits.settle_unknown(
                    session, realm_id, key, status == "executed", self._ctx.config, self._ctx.clock.now()
                )

    def resolve_version_gaps(self) -> None:
        cfg = self._ctx.config.ingest
        now = self._ctx.clock.now()
        with self._ctx.db.transaction() as session:
            gaps = [
                (a.realm_id, a.external_id)
                for a in applications.gaps_older_than(session, now - timedelta(seconds=cfg.version_gap_timeout_seconds))
            ]
        for realm_id, external_id in gaps:
            try:
                body = self._ctx.bank.call("GET", f"/v1/node/applications/{external_id}/snapshot", realm_id=realm_id)
            except AppError:
                continue
            snapshot = ApplicationSnapshot.model_validate(body["snapshot"])
            self._ctx.db.run(partial(self._close_gap, realm_id, external_id, int(body["version"]), snapshot))

    def _close_gap(
        self, realm_id: UUID, external_id: str, version: int, snapshot: ApplicationSnapshot, session: Session
    ) -> None:
        received_at = self._ctx.clock.now()
        realm = realms.resolve(session, realm_id, received_at)
        app = applications.get_visible(session, (realm_id,), external_id)
        ingest.resolve_gap(
            session, self._ctx.intake(), realm, app, version, snapshot, occurred_at=received_at, received_at=received_at
        )

    def deliver_outbox(self) -> None:
        senders = {
            "bank-sim": lambda messages: self._ctx.bank.call(
                "POST", "/v1/node/notifications", json={"messages": messages}
            )
        }
        with self._ctx.db.transaction() as session:
            outbox.deliver_pending(session, self._ctx.config.outbox, senders, self._ctx.clock.now())

    def checkpoints(self) -> None:
        interval = timedelta(seconds=self._ctx.config.audit.checkpoint_interval_seconds)
        now = self._ctx.clock.now()
        with self._ctx.db.transaction() as session:
            for realm_id in audit.realms_needing_checkpoint(session, now - interval):
                audit.create_checkpoint(session, realm_id, self._ctx.signer, now)
        with self._ctx.db.transaction() as session:
            pending = [(c.realm_id, c.seq, c) for c in audit.unanchored(session)]
        for realm_id, seq, checkpoint in pending:
            error = anchoring.send(self._ctx.anchor, checkpoint)
            with self._ctx.db.transaction() as session:
                audit.record_anchor_result(session, realm_id, seq, error, self._ctx.clock.now())

    def delete_inactive_sandboxes(self) -> None:
        ttl = timedelta(hours=self._ctx.config.realms.sandbox_ttl_hours)
        with self._ctx.db.transaction() as session:
            deleted = realms.delete_inactive(session, self._ctx.clock.now(), ttl)
        if deleted:
            log.info("удалены неактивные песочницы: %d", len(deleted))
