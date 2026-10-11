"""Чистая логика дел: конфигурация, очередь и зона по решению, сроки, разрешённые исходами действия."""

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Outcome = Literal["confirmed_fraud", "confirmed_coercion", "reasonable_suspicion", "unable_to_verify", "false_positive"]
ParticipantAction = Literal["hold", "release", "refuse"]
Strategy = Literal["application", "identity", "coordination"]
ZONE_BY_TYPOLOGY = {"F1": 1, "F2": 2, "F3": 3}  # зона = типология ведущей причины (Блок 3)
TYPOLOGY_BY_ZONE = {zone: typology for typology, zone in ZONE_BY_TYPOLOGY.items()}
OPEN = ("open", "in_progress", "escalated")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class QueueRule(_Frozen):
    actions: list[str]
    zones: list[int]


class Deadlines(_Frozen):
    call_hours: int = Field(gt=0)
    group_first_review_hours: int = Field(gt=0)
    participant_decision_days: int = Field(gt=0)


class OutcomeRule(_Frozen):
    """network — что уходит в сеть кредиторов (Блок 4): идентификаторы мошенника или только карта-получатель."""

    application: Literal["refuse", "cancel", "keep_hold", "release"]
    stop_list: bool
    label: Literal["positive", "strong_negative"] | None
    network: Literal["fraudster_identifiers", "recipient_card"] | None = None


class PayrollRule(_Frozen):
    min_applicants: int = Field(gt=0)
    window_days: int = Field(gt=0)
    employer_min_age_days: int = Field(ge=0)


class BatchRule(_Frozen):
    window_days: int = Field(gt=0)
    max_price_robust_z: float
    supplier_min_age_days: int = Field(ge=0)


class BenignConfig(_Frozen):
    household: dict[str, int]
    payroll_project: PayrollRule
    program_batch: BatchRule


class CasesConfig(_Frozen):
    version: str
    queues: dict[str, QueueRule]
    deadlines: Deadlines
    outcomes: dict[Outcome, OutcomeRule]
    participant_actions: list[ParticipantAction]
    participant_roles: list[str]
    checklists: dict[str, list[str]]
    benign: BenignConfig
    retro_search_months: int = Field(gt=0)
    stop_list_kinds: list[str]


def queue_for(config: CasesConfig, action: str) -> str | None:
    return next((name for name, rule in config.queues.items() if action in rule.actions), None)


def due_at(config: CasesConfig, queue: str, now: datetime) -> datetime:
    """Срок первичного разбора: звонок аналитика — в течение рабочего дня, дело группы — 1 рабочий день."""
    hours = config.deadlines.call_hours if queue == "online" else config.deadlines.group_first_review_hours
    return now + timedelta(hours=hours)


def strategy_of(independent_links: int, burst: bool, coordination_flagged: bool) -> Strategy:
    if independent_links or burst:
        return "identity"
    return "coordination" if coordination_flagged else "application"


NOT_LABELED_ROLES = frozenset({"victim", "uninvolved"})  # при фроде метку не получают жертва и посторонний
