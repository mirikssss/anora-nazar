"""Схемы входа и выхода API модуля."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class OperationIn(BaseModel):
    application_id: str = Field(min_length=1, max_length=32)
    operation_type: Literal["disbursement", "supplier_payment"]
    tranche: int = Field(default=1, ge=1)


class OperationOut(BaseModel):
    operation_key: str
    application_id: str
    application_version: int
    operation_type: str
    tranche: int
    amount: int
    account: str
    status: str
    permit: dict[str, Any] | None
    refusal: dict[str, Any] | None
    outcome_reported: bool
    created_at: datetime
    updated_at: datetime


class OperationStatusOut(BaseModel):
    status: Literal["executed", "not_executed", "in_progress"]
