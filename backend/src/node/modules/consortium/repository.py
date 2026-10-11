"""Доступ к таблицам модуля."""

from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from node.modules.consortium.models import NetworkNotification, NetworkObservationRow, NetworkToken


def cached_tokens(session: Session, keys: Iterable[tuple[str, str]]) -> dict[tuple[str, str], NetworkToken]:
    wanted = list(set(keys))
    if not wanted:
        return {}
    rows = session.scalars(select(NetworkToken).where(tuple_(NetworkToken.kind, NetworkToken.value_key).in_(wanted)))
    return {(r.kind, r.value_key): r for r in rows}


def save_tokens(session: Session, rows: list[dict[str, Any]]) -> None:
    if rows:
        session.execute(insert(NetworkToken).values(rows).on_conflict_do_nothing())


def record_notification(session: Session, row: dict[str, Any]) -> bool:
    """True — уведомление новое; повтор доставки возвращает False."""
    result = session.execute(
        insert(NetworkNotification).values(row).on_conflict_do_nothing().returning(NetworkNotification.notification_id)
    )
    return result.first() is not None


def observations(session: Session, keys: list[tuple[UUID, datetime]]) -> dict[tuple[UUID, datetime], dict[str, Any]]:
    if not keys:
        return {}
    rows = session.scalars(
        select(NetworkObservationRow).where(
            tuple_(NetworkObservationRow.application_id, NetworkObservationRow.as_of).in_(keys)
        )
    )
    return {(r.application_id, r.as_of): r.observation for r in rows}


def save_observations(session: Session, rows: list[dict[str, Any]]) -> None:
    if rows:
        session.execute(insert(NetworkObservationRow).values(rows).on_conflict_do_nothing())


def notifications_count(session: Session, realm_id: UUID) -> int:
    query = select(func.count()).select_from(NetworkNotification).where(NetworkNotification.realm_id == realm_id)
    return int(session.scalar(query) or 0)
