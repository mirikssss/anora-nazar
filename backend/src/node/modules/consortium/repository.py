"""Доступ к таблицам модуля."""

from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from node.modules.consortium.models import NetworkNotification, NetworkObservationRow, NetworkToken

CHUNK = 5000  # строк на запрос: PostgreSQL принимает не больше 65 535 параметров (история — десятки тысяч заявок)


def _chunks(items: list[Any]) -> Iterable[list[Any]]:
    for start in range(0, len(items), CHUNK):
        yield items[start : start + CHUNK]


def cached_tokens(session: Session, keys: Iterable[tuple[str, str]]) -> dict[tuple[str, str], NetworkToken]:
    found: dict[tuple[str, str], NetworkToken] = {}
    for chunk in _chunks(list(set(keys))):
        query = select(NetworkToken).where(tuple_(NetworkToken.kind, NetworkToken.value_key).in_(chunk))
        found |= {(r.kind, r.value_key): r for r in session.scalars(query)}
    return found


def save_tokens(session: Session, rows: list[dict[str, Any]]) -> None:
    for chunk in _chunks(rows):
        session.execute(insert(NetworkToken).values(chunk).on_conflict_do_nothing())


def record_notification(session: Session, row: dict[str, Any]) -> bool:
    """True — уведомление новое; повтор доставки возвращает False."""
    result = session.execute(
        insert(NetworkNotification).values(row).on_conflict_do_nothing().returning(NetworkNotification.notification_id)
    )
    return result.first() is not None


def observations(session: Session, keys: list[tuple[UUID, datetime]]) -> dict[tuple[UUID, datetime], dict[str, Any]]:
    found: dict[tuple[UUID, datetime], dict[str, Any]] = {}
    for chunk in _chunks(keys):
        query = select(NetworkObservationRow).where(
            tuple_(NetworkObservationRow.application_id, NetworkObservationRow.as_of).in_(chunk)
        )
        found |= {(r.application_id, r.as_of): r.observation for r in session.scalars(query)}
    return found


def save_observations(session: Session, rows: list[dict[str, Any]]) -> None:
    for chunk in _chunks(rows):
        session.execute(insert(NetworkObservationRow).values(chunk).on_conflict_do_nothing())


def notifications_count(session: Session, realm_id: UUID) -> int:
    query = select(func.count()).select_from(NetworkNotification).where(NetworkNotification.realm_id == realm_id)
    return int(session.scalar(query) or 0)
