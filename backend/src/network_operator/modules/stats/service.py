"""Сводка для страницы риск-менеджера (через узел): по каждому кредитору в общем мире и в песочнице запроса."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from network_operator.modules.activity import service as activity
from network_operator.modules.clients import service as clients
from network_operator.modules.confirmed import service as confirmed
from network_operator.modules.quotas import service as quotas
from network_operator.modules.stats.schemas import LenderStatsOut, NotificationsOut, QuotaOut, StatsOut
from network_operator.modules.watches import service as watches
from network_operator.settings import QuotasConfig


def stats(session: Session, realm_id: UUID | None, limits: QuotasConfig, now: datetime) -> StatsOut:
    realms: list[UUID | None] = [None] if realm_id is None else [None, realm_id]
    events = activity.totals(session, realm_id)
    results = confirmed.totals(session, realm_id)
    queries = quotas.totals(session, realms, "query")
    evaluations = quotas.totals(session, realms, "oprf")
    watching = watches.active_watches(session, realm_id, now)
    delivery = watches.notification_totals(session, realm_id)
    since = quotas.window_start(limits, now)
    lenders = clients.lenders(session)
    rows: list[LenderStatsOut] = []
    for realm in realms:
        for lender in lenders:
            key = (lender, realm)
            applications_now = activity.applications_since(session, lender, realm, since)
            allowance = quotas.allowance(session, lender, realm, applications_now, limits, now)
            pending, delivered, failed = delivery.get(key, (0, 0, 0))
            rows.append(
                LenderStatsOut(
                    lender=lender,
                    contour="world" if realm is None else "sandbox",
                    events=events.get(key, (0, 0))[0],
                    applications=events.get(key, (0, 0))[1],
                    confirmed_results=results.get(key, 0),
                    queries=queries.get(key, (0, 0))[0],
                    oprf_evaluations=evaluations.get(key, (0, 0))[1],
                    quota=QuotaOut(used=allowance.used, limit=allowance.limit, window_seconds=allowance.window_seconds),
                    active_watches=watching.get(key, 0),
                    notifications=NotificationsOut(pending=pending, delivered=delivered, failed=failed),
                )
            )
    return StatsOut(generated_at=now, realm_id=realm_id, lenders=rows)
