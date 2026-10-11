"""Схемы входа и выхода API модуля."""

from typing import Literal

from pydantic import BaseModel, Field


class SessionEventIn(BaseModel):
    pinfl: str = Field(pattern=r"^\d{14}$")
    event_type: Literal["new_device", "access_recovery", "remote_control"]
    device_id: str | None = Field(default=None, min_length=1, max_length=128)


class SessionEventOut(BaseModel):
    session_event_id: str
