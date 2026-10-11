"""Таблицы модуля.

Строка activity_events — принятое сообщение кредитора. У исходного события и у каждого исправления своя строка
с полным набором токенов и интервалом действия [received_at, superseded_at ∧ retracted_at): так счётчик на любой
момент берёт ровно ту версию, что действовала тогда (point-in-time). Отмена (retraction) хранится строкой без
токенов — для дублей — и закрывает интервал всех версий события.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Identity, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from network_operator.database import Base


class ActivityEventRow(Base):
    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    lender: Mapped[str] = mapped_column(String(16))
    realm_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))  # NULL — общий мир
    event_id: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(16))  # тип сообщения как прислан
    refers_to: Mapped[str | None] = mapped_column(String(128))
    root_id: Mapped[int | None] = mapped_column(BigInteger)  # строка исходного события; у него самого — свой id
    fact_kind: Mapped[str | None] = mapped_column(String(16))  # что считается: заявка, выдача, перевод; у отмены NULL
    channel: Mapped[str | None] = mapped_column(String(16))
    subject_token: Mapped[str | None] = mapped_column(String(64))
    credit_share: Mapped[float | None] = mapped_column(Float)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint(
            "lender", "realm_id", "event_id", name="uq_activity_events_event", postgresql_nulls_not_distinct=True
        ),
        Index("ix_activity_events_root_id", "root_id"),
        Index("ix_activity_events_realm_id", "realm_id"),
        Index("ix_activity_events_lender_facts", "lender", "realm_id", "fact_kind", "received_at"),
    )


class ActivityToken(Base):
    """Токен версии события, включая токен ПИНФЛ заявителя: по нему ищутся совпадения."""

    __tablename__ = "activity_tokens"

    event_pk: Mapped[int] = mapped_column(ForeignKey("activity_events.id", ondelete="CASCADE"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    key_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), primary_key=True)

    __table_args__ = (Index("ix_activity_tokens_lookup", "kind", "key_version", "token"),)
