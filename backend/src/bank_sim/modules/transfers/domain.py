"""Чистая логика транзакционного антифрода банка: решение по рекомендации узла (Т3) и своё правило без узла."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TransferStatus = Literal["executed", "held", "cancelled"]
DecidedBy = Literal["node", "own_rule"]

# Рекомендуемое действие узла → что делает ТАФ. Решение за банком (ревью A): узел только рекомендует.
NODE_ACTIONS: dict[str, TransferStatus] = {"allow": "executed", "hold_until_confirmed": "held"}
SECONDS_PER_HOUR = 3600


class OwnRule(BaseModel):
    """Своё правило ТАФ, когда узел недоступен; значения — config/bank_sim.yaml."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    window_hours: float = Field(gt=0)
    min_credit_share: float = Field(ge=0, le=1)
    new_recipient_only: bool


class NodeRecommendation(BaseModel):
    """Ответ узла на Т3; лишние поля не нужны ТАФ и отбрасываются."""

    recommendation_id: str
    level: Literal["green", "yellow", "red"]
    recommended_action: str
    reasons: list[dict[str, Any]]


@dataclass(frozen=True)
class OwnRuleResult:
    hold: bool
    credit_share: float
    hours_since_credit: float
    recipient_is_new: bool

    def as_record(self, rule: OwnRule) -> dict[str, Any]:
        return {
            "hold": self.hold,
            "credit_share": self.credit_share,
            "hours_since_credit": self.hours_since_credit,
            "recipient_is_new": self.recipient_is_new,
            "rule": rule.model_dump(),
        }


def credit_share(amount: int, balance_before_credit: int) -> float:
    """Доля кредитных денег в переводе: часть суммы сверх остатка, который был на карте до зачисления."""
    return round(max(amount - balance_before_credit, 0) / amount, 4)


def apply_own_rule(
    rule: OwnRule,
    *,
    amount: int,
    balance_before_credit: int,
    recipient_is_new: bool,
    credited_at: datetime,
    now: datetime,
) -> OwnRuleResult:
    """Удержать, если вскоре после зачисления большая доля кредита уходит (на новую карту — по правилу)."""
    share = credit_share(amount, balance_before_credit)
    hours = round((now - credited_at).total_seconds() / SECONDS_PER_HOUR, 2)
    hold = (
        hours <= rule.window_hours
        and share >= rule.min_credit_share
        and (recipient_is_new or not rule.new_recipient_only)
    )
    return OwnRuleResult(hold=hold, credit_share=share, hours_since_credit=hours, recipient_is_new=recipient_is_new)


def status_from_recommendation(recommendation: NodeRecommendation | None) -> TransferStatus | None:
    """Решение ТАФ по рекомендации узла; нет рекомендации или действие незнакомо — решает своё правило."""
    if recommendation is None:
        return None
    return NODE_ACTIONS.get(recommendation.recommended_action)
