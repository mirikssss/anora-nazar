"""Чистая логика модуля: какие подписки задело новое событие и срок подписки."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

WatchKey = tuple[str, UUID | None, str]  # (кредитор, контур, ref)


@dataclass(frozen=True)
class PendingNotification:
    id: UUID
    lender: str
    realm_id: UUID | None
    ref: str
    kinds: list[str]
    occurred_at: datetime
    attempts: int


@dataclass(frozen=True)
class WatchHit:
    lender: str
    realm_id: UUID | None
    ref: str
    kind: str


def group_hits(hits: Iterable[WatchHit]) -> dict[WatchKey, list[str]]:
    """Одно уведомление на заявку ref: все типы совпавших токенов вместе."""
    grouped: dict[WatchKey, set[str]] = defaultdict(set)
    for hit in hits:
        grouped[(hit.lender, hit.realm_id, hit.ref)].add(hit.kind)
    return {key: sorted(kinds) for key, kinds in grouped.items()}


def capped_until(requested: datetime, now: datetime, max_seconds: int) -> datetime:
    return min(requested, now + timedelta(seconds=max_seconds))


def next_attempt(now: datetime, retry_seconds: int) -> datetime:
    return now + timedelta(seconds=retry_seconds)
