"""Доступ к таблицам модуля."""

from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, distinct, func, insert, select, tuple_
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from node.modules.index.models import Occurrence, ProgramContract

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


def role_times(
    session: Session, realm_ids: tuple[UUID, ...], kind: str, key: str, since: datetime, as_of: datetime
) -> list[datetime]:
    """Когда банк впервые узнал о каждой заявке с этим атрибутом в окне."""
    rows = session.execute(
        select(func.min(Occurrence.received_at))
        .where(_window(realm_ids, since, as_of), Occurrence.attr_kind == kind, Occurrence.attr_key == key)
        .group_by(Occurrence.application_id)
    )
    return [seen for (seen,) in rows]


def kind_totals(
    session: Session, realm_ids: tuple[UUID, ...], kind: str, since: datetime, until: datetime
) -> tuple[int, int]:
    """Сколько заявок и сколько разных значений атрибута этого вида в окне."""
    row = session.execute(
        select(func.count(distinct(Occurrence.application_id)), func.count(distinct(Occurrence.attr_key))).where(
            _window(realm_ids, since, until), Occurrence.attr_kind == kind
        )
    ).one()
    return int(row[0]), int(row[1])


def holders(
    session: Session, realm_ids: tuple[UUID, ...], kind: str, key: str, since: datetime, as_of: datetime
) -> dict[UUID, str]:
    """Заявки с этим атрибутом в окне и их заявители: заявка → ключ человека."""
    rows = session.execute(
        select(Occurrence.application_id, Occurrence.subject_key)
        .where(_window(realm_ids, since, as_of), Occurrence.attr_kind == kind, Occurrence.attr_key == key)
        .distinct()
    )
    return {app: subject for app, subject in rows}


def own_attributes(
    session: Session, application_id: UUID, kinds: Iterable[str], as_of: datetime
) -> dict[str, tuple[str, str]]:
    """Атрибуты заявки по видам из последней версии, полученной к as_of: вид → (ключ, маска)."""
    rows = session.execute(
        select(Occurrence.attr_kind, Occurrence.attr_key, Occurrence.attr_display)
        .where(
            Occurrence.application_id == application_id,
            Occurrence.attr_kind.in_(list(kinds)),
            Occurrence.received_at <= as_of,
        )
        .order_by(Occurrence.application_version)
    )
    return {kind: (key, display) for kind, key, display in rows}


def add_contract(session: Session, row: dict[str, Any]) -> None:
    session.execute(insert(ProgramContract), [row])


def _contracts(realm_ids: tuple[UUID, ...], since: datetime, as_of: datetime) -> Any:
    """Последняя версия каждой программной заявки, известная к as_of, в окне."""
    return (
        select(ProgramContract)
        .where(
            ProgramContract.realm_id.in_(realm_ids),
            ProgramContract.received_at > since,
            ProgramContract.received_at <= as_of,
        )
        .ext(distinct_on(ProgramContract.application_id))
        .order_by(ProgramContract.application_id, ProgramContract.application_version.desc())
    )


def contract_counts(
    session: Session,
    realm_ids: tuple[UUID, ...],
    group_by: str,
    since: datetime,
    as_of: datetime,
    **where: str,
) -> dict[str, int]:
    """Сколько программных заявок на каждое значение роли group_by, с фильтром по другим ролям."""
    latest = _contracts(realm_ids, since, as_of).subquery()
    column = latest.c[group_by]
    stmt = select(column, func.count()).select_from(latest).group_by(column)
    for name, value in where.items():
        stmt = stmt.where(latest.c[name] == value)
    return {key: count for key, count in session.execute(stmt) if key is not None}


def comparable_prices(
    session: Session,
    realm_ids: tuple[UUID, ...],
    exclude_application: UUID,
    item_code: str,
    unit: str,
    district: str | None,
    since: datetime,
    as_of: datetime,
) -> list[int]:
    """Цены сравнимых договоров: последняя версия каждой другой заявки, известная к as_of."""
    latest = _contracts(realm_ids, since, as_of).where(
        ProgramContract.item_code == item_code,
        ProgramContract.unit == unit,
        ProgramContract.application_id != exclude_application,
    )
    if district is not None:
        latest = latest.where(ProgramContract.district == district)
    return [row.unit_price for row in session.scalars(latest)]
