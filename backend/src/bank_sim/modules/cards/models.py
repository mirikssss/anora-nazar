"""Таблицы модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from bank_sim.database import Base


class CardAccount(Base):
    """Карточный счёт клиента в песочнице: на него зачисляется онлайн-кредит, с него уходят переводы."""

    __tablename__ = "card_accounts"

    realm_id: Mapped[UUID] = mapped_column(ForeignKey("sandboxes.id", ondelete="CASCADE"), primary_key=True)
    account: Mapped[str] = mapped_column(String(64), primary_key=True)
    pinfl: Mapped[str] = mapped_column(String(14))
    balance: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CardCredit(Base):
    """Зачисление кредита по заявке: когда и сколько, и сколько было на карте до него — контекст для Т3."""

    __tablename__ = "card_credits"

    realm_id: Mapped[UUID] = mapped_column(ForeignKey("sandboxes.id", ondelete="CASCADE"), primary_key=True)
    application_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    account: Mapped[str] = mapped_column(String(64))
    pinfl: Mapped[str] = mapped_column(String(14))
    amount: Mapped[int] = mapped_column(BigInteger)
    balance_before: Mapped[int] = mapped_column(BigInteger)
    credited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CardRecipient(Base):
    """Карта, на которую клиент уже переводил: «новый получатель» — карты здесь нет."""

    __tablename__ = "card_recipients"

    realm_id: Mapped[UUID] = mapped_column(ForeignKey("sandboxes.id", ondelete="CASCADE"), primary_key=True)
    pinfl: Mapped[str] = mapped_column(String(14), primary_key=True)
    card: Mapped[str] = mapped_column(String(16), primary_key=True)
    first_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
