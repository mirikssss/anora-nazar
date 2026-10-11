"""Подписки и уведомления: запрос счётчиков с watch_until подписывает заявку на её токены; событие другого
кредитора с тем же токеном кладёт уведомление в outbox в транзакции события; доставку ведёт фоновая задача."""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from network_operator.modules.watches import domain, repository
from network_operator.modules.watches.domain import PendingNotification, WatchHit
from network_operator.settings import NotificationsConfig

TokenKey = tuple[str, int, str]
MAX_ERROR_LENGTH = 512


def subscribe(
    session: Session,
    *,
    lender: str,
    realm_id: UUID | None,
    ref: str,
    tokens: Sequence[TokenKey],
    until: datetime,
    now: datetime,
) -> None:
    repository.upsert_watches(
        session,
        [
            {
                "lender": lender,
                "realm_id": realm_id,
                "ref": ref,
                "kind": kind,
                "key_version": version,
                "token": token,
                "created_at": now,
                "watch_until": until,
            }
            for kind, version, token in dict.fromkeys(tokens)
        ],
    )


def capped_until(requested: datetime, now: datetime, max_seconds: int) -> datetime:
    return domain.capped_until(requested, now, max_seconds)


def notify(
    session: Session,
    *,
    lender: str,
    realm_id: UUID | None,
    event_root: int,
    tokens: Sequence[TokenKey],
    occurred_at: datetime,
    received_at: datetime,
) -> None:
    """Подписки, действовавшие в момент получения события; события прогона истории старше подписок и их не задевают."""
    if not tokens:
        return
    found = [
        WatchHit(r.lender, r.realm_id, r.ref, r.kind)
        for r in repository.hits(session, lender, realm_id, tokens, received_at)
    ]
    repository.add_notifications(
        session,
        [
            {
                "id": uuid4(),
                "lender": watch_lender,
                "realm_id": watch_realm,
                "ref": ref,
                "event_root": event_root,
                "kinds": kinds,
                "occurred_at": occurred_at,
                "created_at": received_at,
                "attempts": 0,
                "next_attempt_at": received_at,
                "delivered_at": None,
                "failed_at": None,
                "last_error": None,
            }
            for (watch_lender, watch_realm, ref), kinds in domain.group_hits(found).items()
        ],
    )


def due(session: Session, now: datetime, limit: int, held: Sequence[UUID]) -> list[PendingNotification]:
    """Уведомления к доставке; контуры с выключенной сетью ждут."""
    return [
        PendingNotification(n.id, n.lender, n.realm_id, n.ref, list(n.kinds), n.occurred_at, n.attempts)
        for n in repository.due(session, now, limit, held)
    ]


def delivered(session: Session, notification: PendingNotification, now: datetime) -> None:
    repository.mark(session, notification.id, delivered_at=now, attempts=notification.attempts + 1, last_error=None)


def failed_attempt(
    session: Session, notification: PendingNotification, error: str, now: datetime, config: NotificationsConfig
) -> None:
    """Повтор с паузой; после max_attempts уведомление помечается недоставленным."""
    attempts = notification.attempts + 1
    repository.mark(
        session,
        notification.id,
        attempts=attempts,
        last_error=error[:MAX_ERROR_LENGTH],
        next_attempt_at=domain.next_attempt(now, config.retry_seconds),
        failed_at=now if attempts >= config.max_attempts else None,
    )


def delete_expired(session: Session, now: datetime) -> None:
    repository.delete_expired(session, now)


def active_watches(session: Session, realm_id: UUID | None, now: datetime) -> dict[tuple[str, UUID | None], int]:
    return repository.active_watches(session, realm_id, now)


def notification_totals(session: Session, realm_id: UUID | None) -> dict[tuple[str, UUID | None], tuple[int, int, int]]:
    return repository.notification_totals(session, realm_id)


def delete_realm(session: Session, realm_id: UUID) -> None:
    repository.delete_realm(session, realm_id)
