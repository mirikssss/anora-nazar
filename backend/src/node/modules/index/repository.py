"""Доступ к таблицам модуля."""

from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, distinct, func, insert, select, tuple_
from sqlalchemy.orm import Session

from node.modules.index.models import Occurrence

Pair = tuple[str, str]


def insert_many(session: Session, rows: list[dict[str, Any]]) -> None:
    if rows:
        session.execute(insert(Occurrence), rows)


def _window(realm_ids: tuple[UUID, ...], since: datetime, as_of: datetime) -> Any:
    return and_(Occurrence.realm_id.in_(realm_ids), Occurrence.received_at > since, Occurrence.received_at <= as_of)


def subject_counts(
    session: Session,
    realm_ids: tuple[UUID, ...],
    pairs: Iterable[Pair],
    since: datetime,
    as_of: datetime,
    *,
    exclude_subject: str | None = None,
) -> dict[Pair, int]:
    """Сколько разных людей с каждым атрибутом в окне; exclude_subject — не считать этого человека."""
    pairs = list(set(pairs))
    if not pairs:
        return {}
    conditions = [_window(realm_ids, since, as_of), tuple_(Occurrence.attr_kind, Occurrence.attr_key).in_(pairs)]
    if exclude_subject is not None:
        conditions.append(Occurrence.subject_key != exclude_subject)
    rows = session.execute(
        select(Occurrence.attr_kind, Occurrence.attr_key, func.count(distinct(Occurrence.subject_key)))
        .where(*conditions)
        .group_by(Occurrence.attr_kind, Occurrence.attr_key)
    )
    return {(kind, key): count for kind, key, count in rows}


def applications_with(
    session: Session, realm_ids: tuple[UUID, ...], pairs: Iterable[Pair], since: datetime, as_of: datetime
) -> list[tuple[UUID, str, str, str]]:
    pairs = list(set(pairs))
    if not pairs:
        return []
    rows = session.execute(
        select(Occurrence.application_id, Occurrence.attr_kind, Occurrence.attr_key, Occurrence.subject_key)
        .where(_window(realm_ids, since, as_of), tuple_(Occurrence.attr_kind, Occurrence.attr_key).in_(pairs))
        .distinct()
    )
    return [(app, kind, key, subject) for app, kind, key, subject in rows]


def attributes_of(
    session: Session,
    realm_ids: tuple[UUID, ...],
    application_ids: Iterable[UUID],
    kinds: Iterable[str],
    since: datetime,
    as_of: datetime,
) -> list[tuple[UUID, str, str, str]]:
    ids, kinds = list(set(application_ids)), list(set(kinds))
    if not ids or not kinds:
        return []
    rows = session.execute(
        select(Occurrence.application_id, Occurrence.attr_kind, Occurrence.attr_key, Occurrence.attr_display)
        .where(_window(realm_ids, since, as_of), Occurrence.application_id.in_(ids), Occurrence.attr_kind.in_(kinds))
        .distinct()
    )
    return [(app, kind, key, display) for app, kind, key, display in rows]


def first_seen(session: Session, application_ids: Iterable[UUID]) -> dict[UUID, datetime]:
    ids = list(set(application_ids))
    if not ids:
        return {}
    rows = session.execute(
        select(Occurrence.application_id, func.min(Occurrence.received_at))
        .where(Occurrence.application_id.in_(ids))
        .group_by(Occurrence.application_id)
    )
    return {app: seen for app, seen in rows}


def subjects_of(session: Session, application_ids: Iterable[UUID]) -> set[str]:
    ids = list(set(application_ids))
    if not ids:
        return set()
    return set(session.scalars(select(Occurrence.subject_key).where(Occurrence.application_id.in_(ids)).distinct()))


def has_version(session: Session, application_id: UUID, version: int) -> bool:
    found = session.scalar(
        select(Occurrence.id)
        .where(Occurrence.application_id == application_id, Occurrence.application_version == version)
        .limit(1)
    )
    return found is not None
