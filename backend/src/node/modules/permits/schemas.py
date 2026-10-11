"""Схемы входа и выхода API модуля."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class PermitIn(BaseModel):
    application_id: str = Field(min_length=1, max_length=128, description="Идентификатор заявки у конвейера")
    application_version: int = Field(ge=1)
    operation_type: Literal["disbursement", "supplier_payment"]
    tranche: int = Field(default=1, ge=1)
    amount: int = Field(gt=0)
    account: str = Field(min_length=1, max_length=64)


class SignedPermit(BaseModel):
    payload: dict[str, Any]
    signature: str
    key_id: str


class RefusalOut(BaseModel):
    code: str
    message: str
    details: dict[str, Any]


class PermitOut(BaseModel):
    granted: bool
    permit: SignedPermit | None
    refusal: RefusalOut | None


class OutcomeIn(BaseModel):
    operation_key: str = Field(min_length=1, max_length=128)
    status: Literal["executed", "not_executed"]


class PermitStatusOut(BaseModel):
    operation_key: str
    status: str
    application_id: str
    operation_type: str
    tranche: int
