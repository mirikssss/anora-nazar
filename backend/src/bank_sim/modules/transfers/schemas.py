"""Схемы входа и выхода API модуля."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TransferIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(min_length=1, max_length=32, description="Заявка, по которой зачислен кредит")
    recipient_card: str = Field(pattern=r"^\d{16}$", description="Карта получателя — 16 цифр")
    amount: int = Field(gt=0, description="Сумма перевода, сум")


class TransferDecisionIn(BaseModel):
    """Решение ТАФ банка по удержанному переводу после подтверждения с клиентом."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["release", "cancel"]


class TransferOut(BaseModel):
    transfer_id: str
    application_id: str
    recipient_card: str
    amount: int
    recipient_is_new: bool
    balance_before_credit: int
    credit_share: float
    credited_at: datetime
    status: str = Field(description="executed — исполнен, held — удержан до подтверждения, cancelled — отменён")
    decided_by: str = Field(description="node — по рекомендации узла (Т3), own_rule — своим правилом ТАФ")
    recommendation: dict[str, Any] | None
    node_error: dict[str, Any] | None
    own_rule: dict[str, Any] | None
    resolution: str | None
    created_at: datetime
    updated_at: datetime
