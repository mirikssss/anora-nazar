"""Схемы входа и выхода API модуля."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class ModelVersionOut(BaseModel):
    model_version_id: UUID
    name: str
    typology: str
    points: list[str]
    feature_set_version: str
    created_at: datetime
    status: Literal["active", "shadow", "retired"]
    metrics: dict[str, Any]


class ReleaseOut(BaseModel):
    release_id: UUID
    model_version_id: UUID
    model_name: str
    requested_by: str
    requested_at: datetime
    approved_by: str | None
    approved_at: datetime | None
