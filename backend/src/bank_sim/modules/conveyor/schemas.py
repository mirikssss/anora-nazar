"""Схемы входа и выхода API модуля."""

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from shared.contracts.application import Applicant, Loan, ProgramDetails


class SimulatedChecks(BaseModel):
    """Итоги проверок, которые в банке делают MyID и оператор связи; в демо их задаёт проверяющий."""

    biometry: Literal["passed", "failed"]
    phone_owner_match: bool


class ApplicationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: Literal["online", "program"]
    branch_id: str = Field(min_length=1, max_length=32)
    employee_id: str | None = Field(default=None, min_length=1, max_length=32)
    applicant: Applicant
    loan: Loan
    disbursement_account: str | None = Field(default=None, min_length=1, max_length=64)
    program: ProgramDetails | None = None
    checks: SimulatedChecks
    session_refs: list[str] = Field(default_factory=list, max_length=100)


class ApplicationChange(BaseModel):
    """Изменение условий — новая версия заявки; прежняя оценка становится устаревшей."""

    model_config = ConfigDict(extra="forbid")

    amount: int | None = Field(default=None, gt=0)
    term_months: int | None = Field(default=None, gt=0, le=600)
    disbursement_account: str | None = Field(default=None, min_length=1, max_length=64)
    supplier_account: str | None = Field(default=None, min_length=1, max_length=64)
    unit_price: int | None = Field(default=None, gt=0)
    quantity: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _not_empty(self) -> Self:
        if not self.model_dump(exclude_none=True):
            raise ValueError("Нужно изменить хотя бы одно условие")
        return self


class ApplicationOut(BaseModel):
    id: str
    channel: str
    version: int
    status: str
    node_state: str | None
    snapshot: dict[str, Any]
    last_decision: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class SnapshotOut(BaseModel):
    version: int
    snapshot: dict[str, Any]
