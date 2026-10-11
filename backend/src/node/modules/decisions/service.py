"""API решений: сбор входов, чистая decide(), неизменяемая запись, удержания, журнал, outbox."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from node.modules.applications import service as applications
from node.modules.applications.domain import VersionOutcome
from node.modules.audit import service as audit
from node.modules.decisions import repository
from node.modules.decisions.domain import DecisionInputs, DecisionResult, decide
from node.modules.decisions.models import Decision
from node.modules.decisions.schemas import AssessmentIn
from node.modules.features import service as features
from node.modules.ingest import service as ingest
from node.modules.ingest.service import IntakeContext
from node.modules.outbox import service as outbox
from node.modules.permits import service as permits
from node.modules.policy.domain import PolicyBundle
from node.modules.policy.service import PolicyRegistry
from node.modules.realms.domain import RealmContext
from node.modules.scoring import service as scoring
from shared.crypto.canonical_json import sha256_hex
from shared.errors import ConflictError, NotFoundError, ValidationFailedError
from shared.idempotency import IdempotencyStore

SCOPE = "assessments"
POINT_CHANNEL = {"T1": "online", "T4": "program"}


@dataclass(frozen=True)
class AssessContext:
    intake: IntakeContext
    bundle: PolicyBundle
    idempotency: IdempotencyStore


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
    policy = ctx.bundle.policy
    vector, view = features.compute(session, realm, app.id, as_of, policy)
    inputs = DecisionInputs(
        point=body.point,
        channel=body.snapshot.channel,
        as_of=as_of,
        application_version=body.application_version,
        snapshot=body.snapshot,
        features=vector,
        graph=view,
        scoring=scoring.evaluate(session, body.point, vector.set_version),
        signals={},
    )
    result = decide(inputs, ctx.bundle)
    record = _record(inputs, result, ctx.bundle)
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
    if result.outcome == "assessed" and result.level in ("yellow", "red"):
        basis = [r.model_dump(mode="json") for r in result.reasons if r.level is not None]
        hold = permits.place_hold(
            session,
            realm_id=realm.id,
            application_id=app.id,
            decision_id=decision_id,
            required_check=result.action,
            basis=basis,
            config=ctx.intake.config,
            now=as_of,
        )
        holds = permits.active_holds(session, app.id) if hold is None else [hold]

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


def get_record(session: Session, realm: RealmContext, decision_id: UUID) -> Decision:
    decision = repository.get_visible(session, realm.visible_ids, decision_id)
    if decision is None:
        raise NotFoundError("decision_not_found", "Решение не найдено")
    return decision


def replay(session: Session, realm: RealmContext, decision_id: UUID, registry: PolicyRegistry) -> dict[str, Any]:
    """Воспроизведение: та же чистая функция на сохранённых входах и действовавшей тогда политике."""
    decision = get_record(session, realm, decision_id)
    versions = decision.record["versions"]
    bundle = registry.get(versions["policy"])
    inputs = DecisionInputs.model_validate(decision.record["inputs"])
    replayed = decide(inputs, bundle).model_dump(mode="json")
    stored = decision.record["result"]
    return {
        "decision_id": decision.id,
        "identical": replayed == stored,
        "policy_unchanged": bundle.policy_hash == versions["policy_hash"],
        "stored": stored,
        "replayed": replayed,
    }
