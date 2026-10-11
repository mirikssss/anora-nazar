"""Таблицы модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from bank_sim.database import Base


class SelfBan(Base):
    """Реестр самозапрета (КИАЦ) в песочнице."""

    __tablename__ = "self_bans"

    realm_id: Mapped[UUID] = mapped_column(ForeignKey("sandboxes.id", ondelete="CASCADE"), primary_key=True)
    pinfl: Mapped[str] = mapped_column(String(14), primary_key=True)
    status: Mapped[str] = mapped_column(String(16))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BureauLock(Base):
    """Очередь бюро: после выдачи онлайн-кредита другие кредиторы заблокированы на срок (№ 3759 п. 20)."""

    __tablename__ = "bureau_locks"

    realm_id: Mapped[UUID] = mapped_column(ForeignKey("sandboxes.id", ondelete="CASCADE"), primary_key=True)
    pinfl: Mapped[str] = mapped_column(String(14), primary_key=True)
    locked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
