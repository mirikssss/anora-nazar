"""Таблицы модуля."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from network_operator.database import Base


class RealmOutage(Base):
    """Демо-сбой: оператор отвечает 503 на запросы этого контура, уведомления ему ждут."""

    __tablename__ = "realm_outages"

    realm_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    since: Mapped[datetime] = mapped_column(DateTime(timezone=True))
