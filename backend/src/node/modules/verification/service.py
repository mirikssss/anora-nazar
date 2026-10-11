"""Реакция узла на ответы проверки намерения и на кнопку «Меня просят взять кредит».

Спокойные ответы закрывают удержание «проверка намерения»; тревожный ответ или кнопка — пауза до звонка
аналитика и дело в очереди антифрод-центра. Заявка помечается «нужна новая оценка»: следующая оценка увидит
сигнал клиента и даст красный уровень по правилу продукта.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from node.modules.applications import service as applications
from node.modules.audit import service as audit
from node.modules.cases import service as cases
from node.modules.cases.service import CaseContext, DecisionSummary
from node.modules.permits import service as permits
from node.modules.realms.domain import RealmContext
from node.modules.verification.domain import Verdict, VerificationConfig, verdict
from shared.contracts.facts import IntentAnswers, PressureReported

PRESSURE_CODE = "PRODUCT_CLIENT_REPORTED_PRESSURE"
INTENT_ANSWERS = "client.intent_answers"
PRESSURE_REPORTED = "client.pressure_reported"


@dataclass(frozen=True)
class VerificationContext:
    config: VerificationConfig
    cases: CaseContext


def handles(fact_type: str) -> bool:
    return fact_type in (INTENT_ANSWERS, PRESSURE_REPORTED)


def on_fact(
    session: Session,
    ctx: VerificationContext,
    realm: RealmContext,
    fact_type: str,
    payload: dict[str, Any],
    received_at: datetime,
) -> str | None:
    """Факт приложения банка о заявке своего контура; чужая или неизвестная заявка пропускается."""
    external_id = str(payload["application_id"])
    app_id = applications.find_id(session, realm.id, external_id)
    if app_id is None:
        return None
    if fact_type == PRESSURE_REPORTED:
        PressureReported.model_validate(payload)
        _escalate(session, ctx, realm, app_id, external_id, [{"source": "client_button"}], received_at)
        return "pressure_reported"
    answers = IntentAnswers.model_validate(payload)
    result = verdict(ctx.config, answers.answers)
    audit.append(
        session,
        realm.id,
        "verification.answered",
        {"application_id": external_id, "verdict": result.value, "answers": [a.model_dump() for a in answers.answers]},
        received_at,
    )
    if result is Verdict.CONFIRMED:
        permits.release_holds(
            session,
            realm_id=realm.id,
            application_id=app_id,
            external_id=external_id,
            checks={ctx.config.check},
            actor="client",
            reason="intent_confirmed",
            config=ctx.cases.node,
            now=received_at,
        )
    elif result is Verdict.ALARMING:
        evidence = [{"source": "intent_answers", "answers": [a.model_dump() for a in answers.answers]}]
        _escalate(session, ctx, realm, app_id, external_id, evidence, received_at)
    return result.value


def _escalate(
    session: Session,
    ctx: VerificationContext,
    realm: RealmContext,
    app_id: Any,
    external_id: str,
    evidence: list[dict[str, Any]],
    now: datetime,
) -> None:
    app = applications.lock(session, {app_id})[app_id]
    reason = {"code": PRESSURE_CODE, "typology": "F1", "source": "rule", "evidence": evidence, "level": "red"}
    if app.latest_decision_id is None:
        return
    permits.place_hold(
        session,
        realm_id=realm.id,
        application_id=app_id,
        external_id=external_id,
        decision_id=app.latest_decision_id,
        required_check=ctx.config.escalation,
        basis=[reason],
        config=ctx.cases.node,
        now=now,
    )
    applications.mark_for_reassessment(
        session, realm.id, {app_id}, {"client_signal": evidence, "at": now.isoformat()}, now
    )
    snapshot = applications.snapshot_of(session, app, app.current_version)[0]
    summary = DecisionSummary(
        decision_id=app.latest_decision_id,
        version=app.current_version,
        point=app.assessment_point or "T1",
        level="red",
        action=ctx.config.escalation,
        channel=snapshot.channel,
        amount=snapshot.loan.amount,
        term_months=snapshot.loan.term_months,
        branch_id=snapshot.branch_id,
        employee_id=snapshot.employee_id,
        reasons=[reason],
        features={},
        unavailable_sources=[],
        leading_typology="F1",
        strategy="application",
        linked_applications=[],
    )
    cases.open_for(session, ctx.cases, realm, app_id, external_id, summary, now)


def questions(config: VerificationConfig) -> dict[str, Any]:
    return {
        "version": config.version,
        "questions": [{"code": q.code, "answers": [{"code": a.code} for a in q.answers]} for q in config.questions],
    }


def client_signal(config: VerificationConfig, pressure: dict[str, Any] | None, answers: dict[str, Any] | None) -> bool:
    """Сигнал клиента для правила продукта: нажата кнопка или ответ на проверке намерения тревожный."""
    if pressure is not None:
        return True
    if answers is None:
        return False
    return verdict(config, IntentAnswers.model_validate(answers).answers) is Verdict.ALARMING
