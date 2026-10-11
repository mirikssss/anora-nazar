"""Схемы входа и выхода API модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ExpectedOut(BaseModel):
    level: str
    action: str


class ScenarioOut(BaseModel):
    code: str
    zone: int | None = Field(description="Слепая зона 1–3; null — контрольный сценарий")
    title: str
    summary: str
    expected: ExpectedOut = Field(description="Смысл сценария; уровень считает узел по своей политике и моделям")
    expected_summary: str
    applications: int = Field(description="Сколько заявок создаёт запуск")


class RunApplicationOut(BaseModel):
    person: str = Field(description="Участник сценария")
    application_id: str | None
    channel: str
    status: str | None
    node_state: str | None
    level: str | None
    action: str | None
    last_decision: dict[str, Any] | None
    in_borrower_app: bool = Field(description="Заявка видна в приложении заёмщика")
    error: dict[str, Any] | None


class ScenarioRunOut(BaseModel):
    run_id: UUID
    number: int
    scenario_code: str
    applications: list[RunApplicationOut]
    created_at: datetime
    finished_at: datetime | None
