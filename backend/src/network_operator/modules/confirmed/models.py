"""Таблицы модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from network_operator.database import Base


class ConfirmedResultRow(Base):
    """Результат закрытого дела кредитора: только идентификаторы мошенника, без идентификаторов жертвы."""

    __tablename__ = "confirmed_results"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    lender: Mapped[str] = mapped_column(String(16))
    realm_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    result_id: Mapped[str] = mapped_column(String(128))
    typology: Mapped[str] = mapped_column(String(8))
    confirmation: Mapped[str] = mapped_column(String(32))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint(
            "lender", "realm_id", "result_id", name="uq_confirmed_results_result", postgresql_nulls_not_distinct=True
        ),
        Index("ix_confirmed_results_realm_id", "realm_id"),
    )


class ConfirmedToken(Base):
    __tablename__ = "confirmed_tokens"

    result_pk: Mapped[int] = mapped_column(ForeignKey("confirmed_results.id", ondelete="CASCADE"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    key_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), primary_key=True)

    __table_args__ = (Index("ix_confirmed_tokens_lookup", "kind", "key_version", "token"),)
