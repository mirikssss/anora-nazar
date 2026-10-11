"""Конверт события, общий для всех источников (Блок 1, «Правила событий»)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: UUID
    source: str = Field(min_length=1, max_length=64)
    type: str = Field(min_length=1, max_length=64)
    entity_type: str = Field(min_length=1, max_length=64)
    entity_id: str = Field(min_length=1, max_length=128)
    entity_version: int | None = Field(default=None, ge=1)
    occurred_at: datetime
    caused_by: UUID | None = None
    schema_version: int = Field(ge=1)
    payload: dict[str, Any]
