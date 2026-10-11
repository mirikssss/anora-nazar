"""Таблицы модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
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


class ProgramContract(Base):
    """Программная заявка одной строкой: роли (ключами индекса) и цена за единицу — база концентраций
    и сравнимых покупок своего банка (Блок 3, зона 3)."""

    __tablename__ = "program_contracts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("realms.id", ondelete="CASCADE"))
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    application_version: Mapped[int] = mapped_column(Integer)
    branch_key: Mapped[str] = mapped_column(String(64))
    employee_key: Mapped[str | None] = mapped_column(String(64))
    helper_key: Mapped[str] = mapped_column(String(64))
    supplier_key: Mapped[str] = mapped_column(String(64))
    item_code: Mapped[str] = mapped_column(String(64))
    unit: Mapped[str] = mapped_column(String(32))
    district: Mapped[str] = mapped_column(String(128))
    unit_price: Mapped[int] = mapped_column(BigInteger)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_program_contracts_item", "item_code", "unit", "received_at"),
        Index("ix_program_contracts_branch", "branch_key", "received_at"),
        Index("ix_program_contracts_helper", "helper_key", "received_at"),
        Index("ix_program_contracts_received", "realm_id", "received_at"),
    )


class StopListEntry(Base):
    """Стоп-лист банка: идентификатор из подтверждённого дела (Блок 4) — правило продукта «не ниже красного»."""

    __tablename__ = "stop_list"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("realms.id", ondelete="CASCADE"))
    attr_kind: Mapped[str] = mapped_column(String(32))
    attr_key: Mapped[str] = mapped_column(String(64))
    attr_display: Mapped[str] = mapped_column(String(64))
    case_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_stop_list_attr", "attr_kind", "attr_key"),)
