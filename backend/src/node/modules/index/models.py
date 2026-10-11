"""Таблицы модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from node.database import Base


class Occurrence(Base):
    """Факт появления атрибута: кто, в какой роли, в какой заявке, когда случилось и когда банк узнал.

    Значение атрибута хранится только ключом HMAC и маской: сырые телефоны и адреса индексу не нужны.
    """

    __tablename__ = "occurrences"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("realms.id", ondelete="CASCADE"))
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    application_version: Mapped[int] = mapped_column(Integer)
    subject_key: Mapped[str] = mapped_column(String(64))
    attr_kind: Mapped[str] = mapped_column(String(32))
    attr_key: Mapped[str] = mapped_column(String(64))
    attr_display: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_occurrences_attr", "attr_kind", "attr_key", "received_at"),
        Index("ix_occurrences_application", "application_id"),
        Index("ix_occurrences_realm_received", "realm_id", "received_at"),
    )
