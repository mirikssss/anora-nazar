"""Доступ к таблицам модуля."""

from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from node.modules.applications.models import ACTIVE, Application, ApplicationVersion


def find_id(session: Session, realm_id: UUID, external_id: str) -> UUID | None:
    return session.scalar(
        select(Application.id).where(Application.realm_id == realm_id, Application.external_id == external_id)
    )


def insert_new(session: Session, values: dict[str, Any]) -> UUID | None:
    """Вставляет заявку; при гонке двух первых версий одна вставка не случится — вернётся None."""
    return session.scalar(insert(Application).values(**values).on_conflict_do_nothing().returning(Application.id))


def lock_many(session: Session, ids: Iterable[UUID]) -> dict[UUID, Application]:
    """Блокирует строки строго по возрастанию id — так параллельные транзакции не ждут друг друга по кругу."""
    ordered = sorted(set(ids))
    if not ordered:
        return {}
    rows = session.scalars(
        select(Application).where(Application.id.in_(ordered)).order_by(Application.id).with_for_update()
    )
    return {row.id: row for row in rows}


def insert_version(session: Session, values: dict[str, Any]) -> None:
    session.execute(insert(ApplicationVersion).values(**values))


def version(session: Session, application_id: UUID, number: int) -> ApplicationVersion | None:
    return session.get(ApplicationVersion, (application_id, number))


def mark(session: Session, realm_id: UUID, ids: list[UUID], cause: dict[str, Any], now: datetime) -> list[UUID]:
    rows = session.execute(
        update(Application)
        .where(Application.id.in_(ids), Application.realm_id == realm_id, Application.status == ACTIVE)
        .values(needs_reassessment=True, reassessment_cause=cause, updated_at=now)
        .returning(Application.id)
    )
    return list(rows.scalars())


def _open(realm_id: UUID, now: datetime) -> Any:
    """Открытая заявка своего контура: активна и её оценка ещё в сроке (или оценки ещё нет)."""
    return and_(
        Application.realm_id == realm_id,
        Application.status == ACTIVE,
        or_(Application.assessment_valid_until.is_(None), Application.assessment_valid_until > now),
    )


def open_ids_of_subject(session: Session, realm_id: UUID, subject_key: str, now: datetime) -> list[UUID]:
    return list(
        session.scalars(select(Application.id).where(_open(realm_id, now), Application.subject_key == subject_key))
    )


def open_ids(session: Session, realm_id: UUID, ids: Iterable[UUID], now: datetime) -> set[UUID]:
    wanted = list(set(ids))
    if not wanted:
        return set()
    return set(session.scalars(select(Application.id).where(_open(realm_id, now), Application.id.in_(wanted))))


def by_external(session: Session, realm_ids: tuple[UUID, ...], external_id: str) -> Application | None:
    return session.scalars(
        select(Application).where(Application.realm_id.in_(realm_ids), Application.external_id == external_id)
    ).one_or_none()


def gaps_older_than(session: Session, before: datetime) -> list[Application]:
    return list(
        session.scalars(
            select(Application).where(
                Application.version_gap_since.is_not(None), Application.version_gap_since < before
            )
        )
    )
