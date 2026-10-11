"""Чистая логика модуля: задержка очереди и порядок версий сущностей источников."""

from datetime import datetime
from typing import Literal

from node.modules.applications.domain import VersionOutcome, classify_version

APPLICATION_VERSION = "application.version"
APPLICATION_CANCELLED = "application.cancelled"

IngestOutcome = Literal["applied", "duplicate", "stale", "parked", "stored"]


def lag_seconds(pending_count: int, oldest_pending: datetime | None, reported_at: datetime, now: datetime) -> float:
    """Отставание = насколько старо самое давнее недоставленное событие или сама отметка, что больше."""
    staleness = (now - reported_at).total_seconds()
    backlog = (now - oldest_pending).total_seconds() if pending_count > 0 and oldest_pending is not None else 0.0
    return max(staleness, backlog, 0.0)


def classify_entity(last: int | None, incoming: int) -> VersionOutcome:
    return classify_version(last, incoming)
