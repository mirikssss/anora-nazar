"""Доступ к таблицам модуля."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from network_operator.modules.clients.models import ApiClient


def upsert(session: Session, values: dict[str, Any]) -> None:
    stmt = insert(ApiClient).values(**values)
    session.execute(stmt.on_conflict_do_update(index_elements=[ApiClient.name], set_=dict(stmt.excluded)))


def by_key_hash(session: Session, key_hash: str) -> ApiClient | None:
    return session.scalars(select(ApiClient).where(ApiClient.key_hash == key_hash)).one_or_none()


def lenders(session: Session) -> list[str]:
    return sorted(session.scalars(select(ApiClient.lender).where(ApiClient.lender.is_not(None)).distinct()))
