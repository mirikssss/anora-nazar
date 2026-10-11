"""Ключи идемпотентности в базе: ключ, хеш параметров, сохранённый ответ (заметка 4 «Ядро»).

Тот же ключ с теми же параметрами возвращает прежний ответ, с другими — конфликт 409.
Таблица своя у каждого сервиса; здесь — общая логика поверх неё.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Column, DateTime, ForeignKey, Integer, MetaData, String, Table, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session

from shared.crypto.canonical_json import sha256_hex
from shared.errors import ConflictError


def idempotency_table(metadata: MetaData, realm_table: str) -> Table:
    return Table(
        "idempotency_keys",
        metadata,
        Column(
            "realm_id", PG_UUID(as_uuid=True), ForeignKey(f"{realm_table}.id", ondelete="CASCADE"), primary_key=True
        ),
        Column("scope", String(64), primary_key=True),
        Column("key", String(128), primary_key=True),
        Column("params_hash", String(64), nullable=False),
        Column("status_code", Integer, nullable=True),
        Column("response", JSONB, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )


@dataclass(frozen=True)
class StoredResponse:
    status_code: int
    body: dict[str, Any]


class IdempotencyStore:
    def __init__(self, table: Table) -> None:
        self._table = table

    def begin(
        self, session: Session, *, realm_id: UUID, scope: str, key: str, params: Any, now: datetime
    ) -> StoredResponse | None:
        """Занимает ключ в текущей транзакции. Возвращает сохранённый ответ, если ключ уже отработал.

        Вставка с ON CONFLICT DO NOTHING ставит блокировку на строку ключа: параллельный повтор
        ждёт фиксации первого запроса и видит его ответ.
        """
        params_hash = sha256_hex(params)
        t = self._table
        session.execute(
            insert(t)
            .values(realm_id=realm_id, scope=scope, key=key, params_hash=params_hash, created_at=now)
            .on_conflict_do_nothing()
        )
        row = session.execute(
            select(t.c.params_hash, t.c.status_code, t.c.response)
            .where(t.c.realm_id == realm_id, t.c.scope == scope, t.c.key == key)
            .with_for_update()
        ).one()
        if row.params_hash != params_hash:
            raise ConflictError(
                "idempotency_key_reused",
                "Этот ключ идемпотентности уже использован с другими параметрами",
                {"key": key},
            )
        if row.status_code is None:
            return None
        return StoredResponse(status_code=row.status_code, body=row.response)

    def complete(
        self, session: Session, *, realm_id: UUID, scope: str, key: str, status_code: int, body: dict[str, Any]
    ) -> None:
        t = self._table
        session.execute(
            t.update()
            .where(t.c.realm_id == realm_id, t.c.scope == scope, t.c.key == key)
            .values(status_code=status_code, response=body)
        )
