"""Таблицы модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from node.database import Base


class Label(Base):
    """Метка с происхождением: типология → результат → источник → степень подтверждения → дата получения → допуск.

    Разные источники не сливаются в «фрод = 1»: решение органа, сообщение клиента и вывод контроля — разные записи.
    """

    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("realms.id", ondelete="CASCADE"))
    application_id: Mapped[UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    typology: Mapped[str | None] = mapped_column(String(8))
    kind: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(32))
    confirmation: Mapped[str] = mapped_column(String(16))
    case_key: Mapped[str | None] = mapped_column(String(128))
    trainable: Mapped[bool] = mapped_column(Boolean)
    event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("kind in ('positive', 'strong_negative', 'weak_negative')", name="kind"),
        Index("ix_labels_realm_received", "realm_id", "received_at"),
        Index("ix_labels_application", "application_id"),
    )
