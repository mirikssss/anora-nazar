"""Доступ к таблицам модуля."""

from collections.abc import Iterable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from node.modules.labels.models import Label


def add_many(session: Session, rows: list[dict[str, Any]]) -> None:
    if rows:
        session.execute(insert(Label), rows)


def known_as_of(
    session: Session, realm_ids: tuple[UUID, ...], application_ids: Iterable[UUID], cutoff: datetime
) -> list[Label]:
    ids = list(set(application_ids))
    if not ids:
        return []
    return list(
        session.scalars(
            select(Label).where(
                Label.realm_id.in_(realm_ids),
                Label.application_id.in_(ids),
                Label.received_at <= cutoff,
                Label.trainable.is_(True),
            )
        )
    )


def latest_received(session: Session, realm_ids: tuple[UUID, ...]) -> datetime | None:
    found: datetime | None = session.scalar(
        select(Label.received_at).where(Label.realm_id.in_(realm_ids)).order_by(Label.received_at.desc()).limit(1)
    )
    return found


def applications_with_kind(session: Session, realm_ids: tuple[UUID, ...], kind: str) -> set[UUID]:
    return set(session.scalars(select(Label.application_id).where(Label.realm_id.in_(realm_ids), Label.kind == kind)))
