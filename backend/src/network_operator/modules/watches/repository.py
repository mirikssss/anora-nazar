"""Доступ к таблицам модуля."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Row, delete, func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import InstrumentedAttribute, Session

from network_operator.modules.watches.models import Notification, Watch

W, N = Watch, Notification


def _visible(column: InstrumentedAttribute[UUID | None], realm_id: UUID | None) -> ColumnElement[bool]:
    return column.is_(None) if realm_id is None else (column.is_(None) | (column == realm_id))


def upsert_watches(session: Session, rows: list[dict[str, Any]]) -> None:
    """Повторный запрос продлевает подписку до большего срока."""
    if rows:
        stmt = insert(W).values(rows)
        session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_watches_ref_token",
                set_={"watch_until": func.greatest(W.watch_until, stmt.excluded.watch_until)},
            )
        )


def hits(
    session: Session, event_lender: str, event_realm: UUID | None, tokens: Sequence[tuple[str, int, str]], at: datetime
) -> Sequence[Row[str, UUID | None, str, str]]:
    """Действующие на момент события подписки других кредиторов на его токены. Событие общего мира видят все
    контуры, событие песочницы — только она."""
    stmt = select(W.lender, W.realm_id, W.ref, W.kind).where(
        tuple_(W.kind, W.key_version, W.token).in_(list(tokens)),
        W.lender != event_lender,
        W.created_at <= at,
        W.watch_until >= at,
    )
    if event_realm is not None:
        stmt = stmt.where(W.realm_id == event_realm)
    return session.execute(stmt).all()


def add_notifications(session: Session, rows: list[dict[str, Any]]) -> None:
    if rows:
        session.execute(insert(N).values(rows).on_conflict_do_nothing(constraint="uq_notifications_ref_event"))


def due(session: Session, now: datetime, limit: int, held: Sequence[UUID]) -> list[Notification]:
    stmt = (
        select(N)
        .where(N.delivered_at.is_(None), N.failed_at.is_(None), N.next_attempt_at <= now)
        .order_by(N.next_attempt_at)
        .limit(limit)
    )
    if held:
        stmt = stmt.where(N.realm_id.is_(None) | N.realm_id.not_in(list(held)))
    return list(session.scalars(stmt))


def delete_expired(session: Session, now: datetime) -> None:
    session.execute(delete(W).where(W.watch_until < now))


def active_watches(session: Session, realm_id: UUID | None, now: datetime) -> dict[tuple[str, UUID | None], int]:
    rows = session.execute(
        select(W.lender, W.realm_id, func.count(func.distinct(W.ref)))
        .where(_visible(W.realm_id, realm_id), W.watch_until >= now)
        .group_by(W.lender, W.realm_id)
    )
    return {(r[0], r[1]): int(r[2]) for r in rows}


def notification_totals(session: Session, realm_id: UUID | None) -> dict[tuple[str, UUID | None], tuple[int, int, int]]:
    """(кредитор, контур) → (ждут доставки, доставлены, не доставлены)."""
    rows = session.execute(
        select(
            N.lender,
            N.realm_id,
            func.count().filter(N.delivered_at.is_(None), N.failed_at.is_(None)),
            func.count().filter(N.delivered_at.is_not(None)),
            func.count().filter(N.failed_at.is_not(None)),
        )
        .where(_visible(N.realm_id, realm_id))
        .group_by(N.lender, N.realm_id)
    )
    return {(r[0], r[1]): (int(r[2]), int(r[3]), int(r[4])) for r in rows}


def delete_realm(session: Session, realm_id: UUID) -> None:
    session.execute(delete(W).where(W.realm_id == realm_id))
    session.execute(delete(N).where(N.realm_id == realm_id))


def mark(session: Session, notification_id: UUID, **values: Any) -> None:
    session.execute(update(N).where(N.id == notification_id).values(**values))
