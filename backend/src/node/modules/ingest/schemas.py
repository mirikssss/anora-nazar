"""Схемы входа и выхода API модуля."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from node.modules.ingest.domain import IngestOutcome
from shared.events import EventEnvelope


class EventIn(EventEnvelope):
    pass


class EventResult(BaseModel):
    event_id: UUID
    outcome: IngestOutcome


class WatermarkIn(BaseModel):
    realm_id: UUID
    producer: str = Field(min_length=1, max_length=64)
    pending_count: int = Field(ge=0)
    oldest_pending_occurred_at: datetime | None
    reported_at: datetime


class WatermarksIn(BaseModel):
    items: list[WatermarkIn] = Field(max_length=1000)
