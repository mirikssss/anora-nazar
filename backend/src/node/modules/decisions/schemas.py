"""Схемы входа и выхода API модуля."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from node.modules.policy.reasons import Reason
from shared.contracts.application import ApplicationSnapshot


class AssessmentIn(BaseModel):
    point: Literal["T1", "T4"]
    application_id: str = Field(min_length=1, max_length=128, description="Идентификатор заявки у конвейера")
    application_version: int = Field(ge=1)
    occurred_at: datetime
    snapshot: ApplicationSnapshot


class HoldOut(BaseModel):
    hold_id: UUID
    required_check: str


class DecisionOut(BaseModel):
    decision_id: UUID
    application_id: str
    application_version: int
    point: str
    outcome: Literal["assessed", "stopped_by_norm"]
    level: str | None
    action: str
    reasons: list[Reason]
    valid_until: datetime
    holds: list[HoldOut]
    marked_applications: list[str]


class DecisionRecordOut(BaseModel):
    decision_id: UUID
    application_version: int
    point: str
    as_of: datetime
    record: dict[str, Any]
    record_hash: str


class ReplayOut(BaseModel):
    decision_id: UUID
    identical: bool
    policy_unchanged: bool
    stored: dict[str, Any]
    replayed: dict[str, Any]
