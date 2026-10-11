"""API решений: сбор входов, чистая decide(), неизменяемая запись, удержания, журнал, outbox."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from node.modules.applications import service as applications
from node.modules.applications.domain import VersionOutcome
from node.modules.audit import service as audit
from node.modules.cases import service as cases
from node.modules.cases.domain import strategy_of
from node.modules.cases.service import CaseContext, DecisionSummary
from node.modules.decisions import repository
from node.modules.decisions.domain import DecisionInputs, DecisionResult, TransferInputs, decide
from node.modules.decisions.domain import recommend_transfer as domain_recommend
from node.modules.decisions.models import Decision
from node.modules.decisions.schemas import AssessmentIn
from node.modules.features import service as features
from node.modules.index import service as index
from node.modules.index.domain import GroupView, subject_key
from node.modules.ingest import service as ingest
from node.modules.ingest.service import IntakeContext
from node.modules.outbox import service as outbox
from node.modules.permits import service as permits
from node.modules.policy.domain import PolicyBundle
from node.modules.policy.reasons import LEVEL_ORDER
from node.modules.policy.service import PolicyRegistry
from node.modules.realms.domain import RealmContext
from node.modules.scoring import service as scoring
from node.modules.scoring.service import ModelCache
from node.modules.verification import service as verification
from node.modules.verification.domain import VerificationConfig
from shared.contracts.transfers import TransferRecommendationIn
from shared.crypto.canonical_json import sha256_hex
from shared.errors import ConflictError, NotFoundError, ValidationFailedError
from shared.idempotency import IdempotencyStore

SCOPE = "assessments"
POINT_CHANNEL = {"T1": "online", "T4": "program"}


@dataclass(frozen=True)
class AssessContext:
    intake: IntakeContext
    policies: PolicyRegistry
    idempotency: IdempotencyStore
    models: ModelCache
    cases: CaseContext
    verification: VerificationConfig


def _record(inputs: DecisionInputs, result: DecisionResult, bundle: PolicyBundle) -> dict[str, Any]:
    return {
        "inputs": inputs.model_dump(mode="json"),
        "versions": {
            "policy": bundle.policy.version,
            "policy_hash": bundle.policy_hash,
            "reasons": bundle.catalog_version,
            "reasons_hash": bundle.catalog_hash,
            "feature_set": inputs.features.set_version,
            "models": [s.model_version_id for s in inputs.scoring.scores],
            "shadow_models": [s.model_version_id for s in inputs.scoring.shadow],
        },
        "result": result.model_dump(mode="json"),
    }


def assess(
    session: Session, ctx: AssessContext, realm: RealmContext, body: AssessmentIn, idempotency_key: str, as_of: datetime
) -> dict[str, Any]:
    if POINT_CHANNEL[body.point] != body.snapshot.channel:
        raise ValidationFailedError(
            "point_channel_mismatch", f"Точка {body.point} — для канала «{POINT_CHANNEL[body.point]}»"
        )
    stored = ctx.idempotency.begin(
        session, realm_id=realm.id, scope=SCOPE, key=idempotency_key, params=body.model_dump(mode="json"), now=as_of
    )
    if stored is not None:
        return stored.body

    accepted = ingest.accept_application_version(
        session,
        ctx.intake,
        realm,
        external_id=body.application_id,
        version=body.application_version,
        snapshot=body.snapshot,
        occurred_at=body.occurred_at,
        received_at=as_of,
        authoritative=True,
        trigger=f"assessment:{idempotency_key}",
    )
    if accepted.outcome is VersionOutcome.STALE:
        raise ConflictError(
            "stale_version", "Узлу известна более новая версия заявки", {"known": accepted.application.current_version}
        )
    app = accepted.application
    bundle = ctx.policies.for_realm(session, realm)
    policy = bundle.policy
    computed = features.compute(
        session,
        realm,
        app.id,
        body.point,
        body.snapshot,
        as_of,
        policy,
        ctx.intake.index_key,
        tuple(ctx.cases.config.stop_list_kinds),
    )
    signals = dict(computed.signals)
    if _client_signal(session, ctx, realm, body.application_id, as_of):
        signals["client_reported_pressure"] = True
    inputs = DecisionInputs(
        point=body.point,
        channel=body.snapshot.channel,
        as_of=as_of,
        application_version=body.application_version,
        snapshot=body.snapshot,
        features=computed.vector,
        graph=computed.graph,
        scoring=scoring.evaluate(session, ctx.models, realm, computed.vector, policy.model),
        signals=signals,
    )
    result = decide(inputs, bundle)
    record = _record(inputs, result, bundle)
    record_hash = sha256_hex(record)
    decision_id = uuid4()
    repository.add(
        session,
        Decision(
            id=decision_id,
            realm_id=realm.id,
            application_id=app.id,
            point=body.point,
            application_version=body.application_version,
            as_of=as_of,
            outcome=result.outcome,
            level=result.level,
            action=result.action,
            valid_until=result.valid_until,
            record=record,
            record_hash=record_hash,
        ),
    )
    applications.record_assessment(
        app,
        applications.AssessmentSummary(
            decision_id=decision_id,
            version=body.application_version,
            point=body.point,
            outcome=result.outcome,
            level=result.level,
            valid_until=result.valid_until,
        ),
        as_of,
    )

    holds = []
    verified = cases.verified(session, app.id, body.application_version)
    if result.outcome == "assessed" and result.level in ("yellow", "red") and not verified:
        basis = [r.model_dump(mode="json") for r in result.reasons if r.level is not None]
        hold = permits.place_hold(
            session,
            realm_id=realm.id,
            application_id=app.id,
            external_id=body.application_id,
            decision_id=decision_id,
            required_check=result.action,
            basis=basis,
            config=ctx.intake.config,
            now=as_of,
        )
        holds = permits.active_holds(session, app.id) if hold is None else [hold]
    summary = _summary(decision_id, inputs, result, computed.graph, app.id)
    if holds:
        cases.open_for(session, ctx.cases, realm, app.id, body.application_id, summary, as_of)
    else:
        cases.refresh(session, app.id, body.application_id, summary, as_of)

    identity = {
        "decision_id": str(decision_id),
        "application_id": body.application_id,
        "application_version": body.application_version,
        "point": body.point,
        "outcome": result.outcome,
        "level": result.level,
        "action": result.action,
    }
    trail = {**identity, "record_hash": record_hash, "policy": policy.version}
    audit.append(session, realm.id, "decision.made", trail, as_of)
    outbox.enqueue(session, ctx.intake.config.outbox, realm.id, "decision.made", trail, as_of)

    response = {
        **identity,
        "reasons": [r.model_dump(mode="json") for r in result.reasons],
        "valid_until": result.valid_until.isoformat(),
        "holds": [{"hold_id": str(h.id), "required_check": h.required_check} for h in holds],
        "marked_applications": accepted.marked,
    }
    ctx.idempotency.complete(
        session, realm_id=realm.id, scope=SCOPE, key=idempotency_key, status_code=200, body=response
    )
    return response


def _client_signal(
    session: Session, ctx: AssessContext, realm: RealmContext, external_id: str, as_of: datetime
) -> bool:
    """Сигнал клиента из приложения банка: кнопка «Меня просят» или тревожный ответ проверки намерения."""
    pressure = ingest.latest_fact(session, realm, "client.pressure_reported", as_of, entity_id=external_id)
    answers = ingest.latest_fact(session, realm, "client.intent_answers", as_of, entity_id=external_id)
    return verification.client_signal(ctx.verification, pressure, answers)


def _summary(
    decision_id: UUID, inputs: DecisionInputs, result: DecisionResult, graph: GroupView, app_id: UUID
) -> DecisionSummary:
    leveled = [r for r in result.reasons if r.level is not None]
    leading = max(leveled, key=lambda r: LEVEL_ORDER[r.level or "green"], default=None)
    snapshot = inputs.snapshot
    return DecisionSummary(
        decision_id=decision_id,
        version=inputs.application_version,
        point=inputs.point,
        level=result.level,
        action=result.action,
        channel=snapshot.channel,
        amount=snapshot.loan.amount,
        term_months=snapshot.loan.term_months,
        branch_id=snapshot.branch_id,
        employee_id=snapshot.employee_id,
        reasons=[r.model_dump(mode="json") for r in sorted(leveled, key=lambda r: -LEVEL_ORDER[r.level or "green"])],
        features=dict(inputs.features.values),
        unavailable_sources=list(inputs.features.unavailable_sources),
        leading_typology=leading.typology if leading else None,
        strategy=strategy_of(graph.independent_rare_links, graph.burst, any(c.flagged for c in graph.coordination)),
        linked_applications=[a for a in graph.member_applications if a != app_id],
    )


def get_record(session: Session, realm: RealmContext, decision_id: UUID) -> Decision:
    decision = repository.get_visible(session, realm.visible_ids, decision_id)
    if decision is None:
        raise NotFoundError("decision_not_found", "Решение не найдено")
    return decision


def compare(
    session: Session,
    realm: RealmContext,
    decision_id: UUID,
    registry: PolicyRegistry,
    cache: ModelCache,
    policy_version: str | None,
    model_ids: list[UUID] | None,
) -> dict[str, Any]:
    """Сравнение версий: сохранённые входы решения через другую политику и (или) другие версии моделей."""
    decision = get_record(session, realm, decision_id)
    versions = decision.record["versions"]
    bundle = registry.get(policy_version or versions["policy"], session)
    if decision.record.get("kind") == "transfer_recommendation":
        raise ValidationFailedError("comparison_not_supported", "Сравнение версий — для решений Т1 и Т4")
    inputs = DecisionInputs.model_validate(decision.record["inputs"])
    if model_ids is not None:
        if bundle.policy.model is None:
            raise ValidationFailedError("policy_without_models", f"В политике {bundle.policy.version} нет моделей")
        inputs = inputs.model_copy(
            update={"scoring": scoring.rescore(session, cache, model_ids, inputs.features, bundle.policy.model)}
        )
    compared = decide(inputs, bundle).model_dump(mode="json")
    stored = decision.record["result"]
    return {
        "decision_id": decision.id,
        "policy_version": bundle.policy.version,
        "model_versions": [s.model_version_id for s in inputs.scoring.scores],
        "level_changed": compared["level"] != stored["level"],
        "stored": stored,
        "compared": compared,
    }


def replay(session: Session, realm: RealmContext, decision_id: UUID, registry: PolicyRegistry) -> dict[str, Any]:
    """Воспроизведение: та же чистая функция на сохранённых входах и действовавшей тогда политике."""
    decision = get_record(session, realm, decision_id)
    versions = decision.record["versions"]
    bundle = registry.get(versions["policy"], session)
    if decision.record.get("kind") == "transfer_recommendation":
        replayed = domain_recommend(TransferInputs.model_validate(decision.record["inputs"]), bundle).model_dump(
            mode="json"
        )
    else:
        replayed = decide(DecisionInputs.model_validate(decision.record["inputs"]), bundle).model_dump(mode="json")
    stored = decision.record["result"]
    return {
        "decision_id": decision.id,
        "identical": replayed == stored,
        "policy_unchanged": bundle.policy_hash == versions["policy_hash"],
        "stored": stored,
        "replayed": replayed,
    }


def first_assessed(session: Session, realm_ids: tuple[UUID, ...]) -> list[Decision]:
    return repository.first_assessed(session, realm_ids)


def recommend_transfer(
    session: Session, ctx: AssessContext, realm: RealmContext, body: TransferRecommendationIn, now: datetime
) -> dict[str, Any]:
    """Т3: рекомендация транзакционному антифроду банка; при красном — дело в очереди антифрод-центра."""
    app_id = applications.find_id(session, realm.id, body.application_id)
    if app_id is None:
        raise NotFoundError("application_not_found", "Заявка неизвестна узлу")
    app = applications.get_by_id(session, app_id)
    snapshot, _hash = applications.snapshot_of(session, app, app.current_version)
    subject = subject_key(ctx.intake.index_key, snapshot.applicant.pinfl)
    bundle = ctx.policies.for_realm(session, realm)
    rules = bundle.policy.transfers
    if rules is None:
        raise ValidationFailedError("transfers_not_configured", "В действующей политике нет правил первого перевода")
    card_key, _display = index.record_card(
        session, realm.id, app.id, app.current_version, subject, body.recipient_card, ctx.intake.index_key, now
    )
    inputs = TransferInputs(
        as_of=now,
        application_version=app.current_version,
        loan_amount=snapshot.loan.amount,
        transfer=body,
        recipient_borrowers=index.card_subjects(session, realm, card_key, rules.window_days, now),
        stop_matches=[m.model_dump() for m in index.stop_listed(session, realm, app.id, ["card"], now)],
    )
    result = domain_recommend(inputs, bundle)
    record = {
        "kind": "transfer_recommendation",
        "inputs": inputs.model_dump(mode="json"),
        "versions": {
            "policy": bundle.policy.version,
            "policy_hash": bundle.policy_hash,
            "reasons": bundle.catalog_version,
            "reasons_hash": bundle.catalog_hash,
        },
        "result": result.model_dump(mode="json"),
    }
    decision_id = uuid4()
    repository.add(
        session,
        Decision(
            id=decision_id,
            realm_id=realm.id,
            application_id=app.id,
            point="T3",
            application_version=app.current_version,
            as_of=now,
            outcome="recommended",
            level=result.level,
            action=result.recommended_action,
            valid_until=now,
            record=record,
            record_hash=sha256_hex(record),
        ),
    )
    trail = {
        "decision_id": str(decision_id),
        "application_id": body.application_id,
        "transfer_id": body.transfer_id,
        "point": "T3",
        "level": result.level,
        "recommended_action": result.recommended_action,
    }
    audit.append(session, realm.id, "transfer.recommended", trail, now)
    if result.level == "red":
        summary = DecisionSummary(
            decision_id=decision_id,
            version=app.current_version,
            point="T3",
            level="red",
            action="pause_for_call",
            channel=snapshot.channel,
            amount=body.amount,
            term_months=snapshot.loan.term_months,
            branch_id=snapshot.branch_id,
            employee_id=snapshot.employee_id,
            reasons=[r.model_dump(mode="json") for r in result.reasons],
            features={},
            unavailable_sources=[],
            leading_typology="F1",
            strategy="application",
            linked_applications=[],
        )
        cases.open_for(session, ctx.cases, realm, app.id, body.application_id, summary, now)
    return {"recommendation_id": str(decision_id), **result.model_dump(mode="json")}


def latest_assessment_at(session: Session, realm_ids: tuple[UUID, ...]) -> datetime | None:
    return repository.latest_assessment_at(session, realm_ids)


def level_counts(session: Session, realm_ids: tuple[UUID, ...], since: datetime) -> list[dict[str, Any]]:
    """Доли уровней по дням: остановки по норме — отдельно, без уровня."""
    days: dict[Any, dict[str, Any]] = {}
    for day, level, count in repository.level_counts(session, realm_ids, since):
        row = days.setdefault(day, {"day": day, "green": 0, "yellow": 0, "red": 0, "stopped": 0})
        row[level or "stopped"] += count
    return list(days.values())


def feature_values(
    session: Session, realm_ids: tuple[UUID, ...], since: datetime, names: list[str]
) -> list[tuple[datetime, dict[str, Any]]]:
    return repository.feature_values(session, realm_ids, since, names)
