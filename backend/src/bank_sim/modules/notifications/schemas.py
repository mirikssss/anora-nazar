"""Схемы входа и выхода API модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationIn(BaseModel):
    id: int
    realm_id: UUID
    topic: str
    payload: dict[str, Any]
    created_at: datetime


class NotificationsIn(BaseModel):
    messages: list[NotificationIn] = Field(max_length=1000)


class NotificationOut(BaseModel):
    message_id: int
    topic: str
    payload: dict[str, Any]
    received_at: datetime
