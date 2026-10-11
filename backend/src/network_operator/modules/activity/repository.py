"""Доступ к таблицам модуля."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Row, delete, func, insert, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from network_operator.modules.activity.domain import TokenKey
from network_operator.modules.activity.models import ActivityEventRow, ActivityToken

E = ActivityEventRow


def _visible(realm_id: UUID | None) -> ColumnElement[bool]:
    """Песочница видит общий мир и себя; общий мир — только себя."""
    return E.realm_id.is_(None) if realm_id is None else (E.realm_id.is_(None) | (E.realm_id == realm_id))


def _exact(realm_id: UUID | None) -> ColumnElement[bool]:
    return E.realm_id.is_(None) if realm_id is None else E.realm_id == realm_id


def find(session: Session, lender: str, realm_id: UUID | None, event_id: str) -> ActivityEventRow | None:
    return session.scalars(select(E).where(E.lender == lender, _exact(realm_id), E.event_id == event_id)).one_or_none()


def insert_event(session: Session, values: dict[str, Any]) -> int | None:
    """Новая строка или None, если такой event_id у кредитора в контуре уже есть (параллельный повтор)."""
    stmt = pg_insert(E).values(**values).on_conflict_do_nothing(constraint="uq_activity_events_event").returning(E.id)
    return session.execute(stmt).scalar_one_or_none()


def set_root(session: Session, event_pk: int) -> None:
    session.execute(update(E).where(E.id == event_pk).values(root_id=event_pk))


def add_tokens(session: Session, event_pk: int, tokens: Sequence[TokenKey]) -> None:
    if tokens:
        rows = [{"event_pk": event_pk, "kind": k, "key_version": v, "token": t} for k, v, t in tokens]
        session.execute(insert(ActivityToken), rows)


def versions(session: Session, root_id: int) -> list[ActivityEventRow]:
    """Версии события под блокировкой: исправления и отмены одного события идут по очереди."""
    stmt = select(E).where(E.root_id == root_id, E.fact_kind.is_not(None)).order_by(E.id).with_for_update()
    return list(session.scalars(stmt))


def cut(session: Session, version_id: int, at: datetime) -> None:
    session.execute(update(E).where(E.id == version_id).values(superseded_at=at))


def retract(session: Session, root_id: int, at: datetime) -> None:
    session.execute(
        update(E)
        .where(E.root_id == root_id, E.fact_kind.is_not(None))
        .values(retracted_at=func.least(func.coalesce(E.retracted_at, at), at))
    )


def matching(
    session: Session,
    realm_id: UUID | None,
    exclude_lender: str,
    tokens: Sequence[TokenKey],
    occurred_after: datetime,
    received_until: datetime,
) -> Sequence[Row[str, int, str, ActivityEventRow]]:
    """Версии чужих событий с этими токенами, которые могли действовать в интервале запросов."""
    t = ActivityToken
    stmt = (
        select(t.kind, t.key_version, t.token, E)
        .join(E, E.id == t.event_pk)
        .where(
            tuple_(t.kind, t.key_version, t.token).in_(list(tokens)),
            E.fact_kind.is_not(None),
            E.lender != exclude_lender,
            _visible(realm_id),
            E.received_at <= received_until,
            E.occurred_at > occurred_after,
        )
    )
    return session.execute(stmt).all()


def applications_since(session: Session, lender: str, realm_id: UUID | None, since: datetime) -> int:
    stmt = select(func.count()).where(
        E.lender == lender, _exact(realm_id), E.kind == "application", E.received_at > since
    )
    return int(session.scalar(stmt) or 0)


def totals(session: Session, realm_id: UUID | None) -> dict[tuple[str, UUID | None], tuple[int, int]]:
    """(кредитор, контур) → (событий без исправлений и отмен, из них заявок)."""
    rows = session.execute(
        select(
            E.lender,
            E.realm_id,
            func.count().filter(E.kind.in_(["application", "issuance", "transfer"])),
            func.count().filter(E.kind == "application"),
        )
        .where(_visible(realm_id))
        .group_by(E.lender, E.realm_id)
    )
    return {(r[0], r[1]): (int(r[2]), int(r[3])) for r in rows}


def delete_realm(session: Session, realm_id: UUID) -> None:
    session.execute(delete(E).where(E.realm_id == realm_id))
