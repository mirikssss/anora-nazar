"""Чистая логика разрешений: что проверяет запрос и какие переходы состояний допустимы."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

OperationType = Literal["disbursement", "supplier_payment"]
REQUIRED_POINT: dict[str, str] = {"disbursement": "T1", "supplier_payment": "T4"}


class Refusal(StrEnum):
    APPLICATION_NOT_FOUND = "application_not_found"
    APPLICATION_CANCELLED = "application_cancelled"
    VERSION_GAP = "version_gap"
    QUEUE_LAG = "queue_lag"
    VERSION_MISMATCH = "version_mismatch"
    ASSESSMENT_REQUIRED = "assessment_required"
    REASSESSMENT_REQUIRED = "reassessment_required"
    STOPPED_BY_NORM = "stopped_by_norm"
    WRONG_STAGE = "wrong_stage"
    ASSESSMENT_EXPIRED = "assessment_expired"
    ACTIVE_HOLD = "active_hold"
    CONDITIONS_MISMATCH = "conditions_mismatch"
    OPERATION_IN_PROGRESS = "operation_in_progress"
    ALREADY_EXECUTED = "already_executed"


MESSAGES: dict[Refusal, str] = {
    Refusal.APPLICATION_NOT_FOUND: "Заявка неизвестна узлу",
    Refusal.APPLICATION_CANCELLED: "Заявка отменена",
    Refusal.VERSION_GAP: "Узел ждёт пропущенную версию заявки",
    Refusal.QUEUE_LAG: "Очередь событий отстаёт: картина может быть неполной, операция ждёт",
    Refusal.VERSION_MISMATCH: "Версия заявки не совпадает с известной узлу",
    Refusal.ASSESSMENT_REQUIRED: "Эта версия заявки ещё не оценена",
    Refusal.REASSESSMENT_REQUIRED: "Появился новый факт — нужна новая оценка",
    Refusal.STOPPED_BY_NORM: "Процесс остановлен обязательным правилом",
    Refusal.WRONG_STAGE: "Оценка сделана для другого этапа",
    Refusal.ASSESSMENT_EXPIRED: "Срок годности оценки истёк",
    Refusal.ACTIVE_HOLD: "На заявке действует удержание до проверки",
    Refusal.CONDITIONS_MISMATCH: "Условия операции не совпадают с оценённой заявкой",
    Refusal.OPERATION_IN_PROGRESS: "Эта операция уже зарезервирована или её итог выясняется",
    Refusal.ALREADY_EXECUTED: "Эта операция уже исполнена",
}


@dataclass(frozen=True)
class RefusalResult:
    code: Refusal
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def message(self) -> str:
        return MESSAGES[self.code]


@dataclass(frozen=True)
class PermitRequest:
    application_version: int
    operation_type: OperationType
    tranche: int
    amount: int
    account: str


@dataclass(frozen=True)
class ApplicationFacts:
    status: str
    current_version: int
    assessed_version: int | None
    needs_reassessment: bool
    reassessment_cause: dict[str, Any] | None
    version_gap: bool
    assessment_point: str | None
    assessment_outcome: str | None
    assessment_valid_until: datetime | None


@dataclass(frozen=True)
class OperationFacts:
    allowed_amount: int
    expected_account: str
    existing_statuses: tuple[str, ...]
    active_hold_bases: tuple[dict[str, Any], ...]


def check(  # noqa: PLR0911, PLR0912 — проверки строго по порядку, у каждой свой отказ
    app: ApplicationFacts,
    op: OperationFacts,
    request: PermitRequest,
    now: datetime,
    queue_lag: float | None,
    max_lag: float,
) -> RefusalResult | None:
    """Порядок проверок фиксирован: сначала полнота картины, потом актуальность оценки, потом сама операция."""
    if app.status != "active":
        return RefusalResult(Refusal.APPLICATION_CANCELLED)
    if app.version_gap:
        return RefusalResult(Refusal.VERSION_GAP)
    if queue_lag is None or queue_lag > max_lag:
        return RefusalResult(Refusal.QUEUE_LAG, {"lag_seconds": queue_lag, "max_lag_seconds": max_lag})
    if request.application_version != app.current_version:
        return RefusalResult(
            Refusal.VERSION_MISMATCH, {"requested": request.application_version, "known": app.current_version}
        )
    if app.assessed_version != app.current_version or app.assessment_valid_until is None:
        return RefusalResult(Refusal.ASSESSMENT_REQUIRED)
    if app.needs_reassessment:
        return RefusalResult(Refusal.REASSESSMENT_REQUIRED, {"cause": app.reassessment_cause})
    if app.assessment_outcome == "stopped_by_norm":
        return RefusalResult(Refusal.STOPPED_BY_NORM)
    required = REQUIRED_POINT[request.operation_type]
    if app.assessment_point != required:
        return RefusalResult(Refusal.WRONG_STAGE, {"required": required, "assessed": app.assessment_point})
    if app.assessment_valid_until <= now:
        return RefusalResult(Refusal.ASSESSMENT_EXPIRED, {"valid_until": app.assessment_valid_until.isoformat()})
    if op.active_hold_bases:
        return RefusalResult(Refusal.ACTIVE_HOLD, {"holds": list(op.active_hold_bases)})
    if request.amount > op.allowed_amount or request.account != op.expected_account:
        return RefusalResult(
            Refusal.CONDITIONS_MISMATCH,
            {
                "allowed_amount": op.allowed_amount,
                "amount_matches": request.amount <= op.allowed_amount,
                "account_matches": request.account == op.expected_account,
            },
        )
    if "executed" in op.existing_statuses:
        return RefusalResult(Refusal.ALREADY_EXECUTED)
    if op.existing_statuses:
        return RefusalResult(Refusal.OPERATION_IN_PROGRESS, {"statuses": list(op.existing_statuses)})
    return None


FINAL = {"executed", "not_executed"}


def next_status(current: str, reported: str) -> str | None:
    """Допустимые переходы итога; None — противоречие (итог уже другой)."""
    if current == reported and reported in FINAL:
        return current
    if current in {"reserved", "unknown"} and reported in FINAL:
        return reported
    return None
