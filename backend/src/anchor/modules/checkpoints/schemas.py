"""Схемы входа и выхода API модуля."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CheckpointIn(BaseModel):
    realm_id: UUID
    seq: int = Field(ge=1)
    merkle_root: str = Field(pattern=r"^[0-9a-f]{64}$")
    head_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    signature: str = Field(min_length=1, max_length=128)
    key_id: str = Field(min_length=1, max_length=32)


class CheckpointOut(BaseModel):
    seq: int
    merkle_root: str
    head_hash: str
    created_at: datetime
    received_at: datetime


class CheckpointsOut(BaseModel):
    items: list[CheckpointOut]
