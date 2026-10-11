"""Доступ к таблицам модуля."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Row, delete, func, insert, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from network_operator.modules.confirmed.models import ConfirmedResultRow, ConfirmedToken

R, T = ConfirmedResultRow, ConfirmedToken


def _visible(realm_id: UUID | None) -> ColumnElement[bool]:
    return R.realm_id.is_(None) if realm_id is None else (R.realm_id.is_(None) | (R.realm_id == realm_id))


def find_hash(session: Session, lender: str, realm_id: UUID | None, result_id: str) -> str | None:
    realm = R.realm_id.is_(None) if realm_id is None else R.realm_id == realm_id
    return session.scalar(select(R.content_hash).where(R.lender == lender, realm, R.result_id == result_id))


def insert_result(session: Session, values: dict[str, Any]) -> int | None:
    stmt = (
        pg_insert(R).values(**values).on_conflict_do_nothing(constraint="uq_confirmed_results_result").returning(R.id)
    )
    return session.execute(stmt).scalar_one_or_none()


def add_tokens(session: Session, result_pk: int, tokens: Sequence[tuple[str, int, str]]) -> None:
    rows = [{"result_pk": result_pk, "kind": k, "key_version": v, "token": t} for k, v, t in tokens]
    session.execute(insert(T), rows)


def matching(
    session: Session,
    realm_id: UUID | None,
    exclude_lender: str,
    tokens: Sequence[tuple[str, int, str]],
    until: datetime,
) -> Sequence[Row[str, int, str, ConfirmedResultRow]]:
    stmt = (
        select(T.kind, T.key_version, T.token, R)
        .join(R, R.id == T.result_pk)
        .where(
            tuple_(T.kind, T.key_version, T.token).in_(list(tokens)),
            R.lender != exclude_lender,
            _visible(realm_id),
            R.received_at <= until,
        )
    )
    return session.execute(stmt).all()


def totals(session: Session, realm_id: UUID | None) -> dict[tuple[str, UUID | None], int]:
    rows = session.execute(
        select(R.lender, R.realm_id, func.count()).where(_visible(realm_id)).group_by(R.lender, R.realm_id)
    )
    return {(r[0], r[1]): int(r[2]) for r in rows}


def delete_realm(session: Session, realm_id: UUID) -> None:
    session.execute(delete(R).where(R.realm_id == realm_id))
