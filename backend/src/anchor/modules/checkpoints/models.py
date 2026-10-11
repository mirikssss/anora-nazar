"""Таблицы модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from anchor.database import Base


class Checkpoint(Base):
    """Подписанная контрольная точка журнала узла. Записи только добавляются."""

    __tablename__ = "checkpoints"

    realm_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    merkle_root: Mapped[str] = mapped_column(String(64))
    head_hash: Mapped[str] = mapped_column(String(64))
    signature: Mapped[str] = mapped_column(String(128))
    key_id: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
