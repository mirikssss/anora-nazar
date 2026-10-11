"""Схемы входа и выхода API модуля."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RecordOut(BaseModel):
    seq: int
    kind: str
    payload: dict[str, Any]
    recorded_at: datetime
    prev_hash: str
    hash: str


class CheckpointOut(BaseModel):
    seq: int
    merkle_root: str
    created_at: datetime
    anchored: bool
    anchor_error: str | None


class BreakOut(BaseModel):
    seq: int
    kind: str
    problem: str


class AnchorMismatchOut(BaseModel):
    seq: int
    problem: str


class VerificationOut(BaseModel):
    intact: bool
    records_checked: int
    first_break: BreakOut | None
    checkpoints_checked: int
    anchor_mismatch: AnchorMismatchOut | None
    anchor_reachable: bool
