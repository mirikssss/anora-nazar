"""Схемы входа и выхода API модуля."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from node.modules.cases.domain import Outcome, ParticipantAction
from node.modules.policy.reasons import Level, ReasonSource, Typology

Value = float | int | bool | None


class ReasonOut(BaseModel):
    code: str
    typology: Typology | None
    source: ReasonSource
    level: Level | None
    norm: str | None
    evidence: list[dict[str, Any]]


class CaseApplicationBrief(BaseModel):
    application_id: str
    point: str
    channel: str
    level: str | None
    amount: int
    risk_cost_estimate: float | None
    risk_cost_is_estimate: Literal[True] = True


class CaseListItem(BaseModel):
    case_id: str
    queue: str
    zone: int
    strategy: str
    status: str
    assignee: str | None
    due_at: datetime
    escalated_at: datetime | None
    created_at: datetime
    risk_cost_estimate: float | None
    applications: list[CaseApplicationBrief]


class HoldOut(BaseModel):
    hold_id: str
    required_check: str
    created_at: datetime


class ApplicantView(BaseModel):
    """Персональные данные — маской; полные — по праву pii.full.view и с записью в журнал."""

    pinfl: str
    phone: str
    address: str | None
    full: bool


class CaseApplicationOut(BaseModel):
    application_id: str
    status: str
    point: str
    channel: str
    level: str | None
    action: str
    amount: int
    term_months: int
    risk_cost_estimate: float | None
    reasons: list[ReasonOut]
    features: dict[str, Value]
    unavailable_sources: list[str]
    holds: list[HoldOut]
    applicant: ApplicantView
    decision: str | None
    role: str | None
    basis: str | None
    decided_by: str | None
    decided_at: datetime | None


class TimelineEntry(BaseModel):
    at: datetime
    actor: str
    kind: str
    payload: dict[str, Any]
    audit_seq: int


class BenignOut(BaseModel):
    code: str
    evidence: dict[str, Any]


class ScriptQuestion(BaseModel):
    code: str
    answers: list[str]


class CaseDetailOut(BaseModel):
    case_id: str
    queue: str
    zone: int
    strategy: str
    status: str
    assignee: str | None
    due_at: datetime
    escalated_at: datetime | None
    outcome: str | None
    created_at: datetime
    closed_at: datetime | None
    applications: list[CaseApplicationOut]
    benign: list[BenignOut]
    checklist_items: list[str]
    call_script: list[ScriptQuestion]
    allowed_outcomes: list[str]
    participant_actions: list[str]
    participant_roles: list[str]
    timeline: list[TimelineEntry]


class GraphNodeOut(BaseModel):
    id: str
    type: str
    display: str
    application_id: str | None
    level: str | None


class GraphEdgeOut(BaseModel):
    source: str
    target: str
    type: str
    rare: bool


class CaseGraphOut(BaseModel):
    case_id: str
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]


class ParticipantDecisionIn(BaseModel):
    action: ParticipantAction
    role: str | None = Field(default=None, max_length=32)
    basis: str = Field(min_length=3, max_length=2000)


class OutcomeIn(BaseModel):
    outcome: Outcome
    checklist: dict[str, bool] = Field(default_factory=dict)
    answers: dict[str, str] = Field(default_factory=dict)
    note: str = Field(default="", max_length=4000)


class RetroMatch(BaseModel):
    application_id: str
    shared: list[str]


class RetroSearchOut(BaseModel):
    case_id: str
    matches: list[RetroMatch]
