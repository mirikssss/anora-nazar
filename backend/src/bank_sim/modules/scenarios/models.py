"""Таблицы модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from bank_sim.database import Base


class ScenarioRun(Base):
    """Запуск сценария в песочнице: номер запуска задаёт участников, итог — созданные заявки и их решения."""

    __tablename__ = "scenario_runs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    realm_id: Mapped[UUID] = mapped_column(ForeignKey("sandboxes.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    scenario_code: Mapped[str] = mapped_column(String(64))
    applications: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("realm_id", "number", name="uq_scenario_runs_realm_number"),)
