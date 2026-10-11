"""Таблицы модуля."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from bank_sim.database import Base


class ProgramHelper(Base):
    """Помощник хокима из синтетического мира; отвечает за одну махаллю района. Общий справочник."""

    __tablename__ = "program_helpers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    district: Mapped[str] = mapped_column(String(128), index=True)
    mahalla: Mapped[str] = mapped_column(String(128))


class ProgramSupplier(Base):
    """Поставщик программ из синтетического мира. Общий справочник."""

    __tablename__ = "program_suppliers"

    inn: Mapped[str] = mapped_column(String(9), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64))
    district: Mapped[str] = mapped_column(String(128), index=True)
    registered_on: Mapped[date] = mapped_column(Date)
    account: Mapped[str] = mapped_column(String(64))


class AcceptanceActRecord(Base):
    """Акт приёмки по программной заявке в песочнице: по нему АБС запрашивает оплату поставщику (Т5)."""

    __tablename__ = "acceptance_acts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("sandboxes.id", ondelete="CASCADE"))
    application_id: Mapped[str] = mapped_column(String(32))
    signer_id: Mapped[str] = mapped_column(String(64))
    signer_role: Mapped[str] = mapped_column(String(32))
    signed_on: Mapped[date] = mapped_column(Date)
    invoice_amount: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_acceptance_acts_realm_application", "realm_id", "application_id"),)
