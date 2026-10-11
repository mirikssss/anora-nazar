"""Т3 — первый перевод кредитных денег: транзакционный антифрод банка спрашивает рекомендацию узла и решает сам."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RecommendedAction = Literal["allow", "hold_until_confirmed"]


class TransferRecommendationIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    application_id: str = Field(min_length=1, max_length=128)
    transfer_id: str = Field(min_length=1, max_length=64)
    amount: int = Field(gt=0)
    recipient_card: str = Field(pattern=r"^\d{16}$")
    recipient_is_new: bool
    balance_before_credit: int = Field(ge=0)
    credited_at: datetime
    requested_at: datetime
