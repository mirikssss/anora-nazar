"""Разрешения на операции: проверка и резерв одной транзакцией, удержания, итоги, просрочка и сверка."""

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from node.modules.applications import service as applications
from node.modules.audit import service as audit
from node.modules.outbox import service as outbox
from node.modules.permits import repository
from node.modules.permits.domain import (
    ApplicationFacts,
    OperationFacts,
    PermitRequest,
    Refusal,
    RefusalResult,
    check,
    next_status,
)
from node.modules.permits.models import NOT_EXECUTED, RESERVED, UNKNOWN, Hold, Permit
from node.settings import NodeConfig
from shared.crypto.signing import Signer
from shared.errors import ConflictError, NotFoundError
from shared.idempotency import IdempotencyStore

SCOPE = "permits"


def _refused(result: RefusalResult) -> dict[str, Any]:
    return {
        "granted": False,
        "permit": None,
        "refusal": {"code": result.code.value, "message": result.message, "details": result.details},
    }


def _operation_facts(
    session: Session, app_id: UUID, snapshot: dict[str, Any] | None, request: PermitRequest, holds: list[Hold]
) -> OperationFacts:
    if snapshot is None:
        total, account = 0, ""
    elif request.operation_type == "disbursement":
        total, account = int(snapshot["loan"]["amount"]), str(snapshot.get("disbursement_account") or "")
    else:
        program = snapshot.get("program") or {}
        total = int(program.get("unit_price", 0)) * int(program.get("quantity", 0))
        account = str(program.get("supplier_account", ""))
    spent = repository.executed_amount(session, app_id, request.operation_type, request.tranche)
    return OperationFacts(
        allowed_amount=max(total - spent, 0),
        expected_account=account,
        existing_statuses=tuple(repository.statuses_for(session, app_id, request.operation_type, request.tranche)),
        active_hold_bases=tuple(
            {"hold_id": str(h.id), "required_check": h.required_check, "basis": h.basis} for h in holds
        ),
    )


def request_permit(
    session: Session,
    *,
    realm_id: UUID,
    external_id: str,
    operation_key: str,
    request: PermitRequest,
    now: datetime,
    queue_lag: float | None,
    config: NodeConfig,
    signer: Signer,
    idempotency: IdempotencyStore,
) -> dict[str, Any]:
    params = {"application_id": external_id, **asdict(request)}
    stored = idempotency.begin(session, realm_id=realm_id, scope=SCOPE, key=operation_key, params=params, now=now)
    if stored is not None:
        return stored.body

    body = _decide(
        session,
        realm_id=realm_id,
        external_id=external_id,
        operation_key=operation_key,
        request=request,
        now=now,
        queue_lag=queue_lag,
        config=config,
        signer=signer,
    )
    idempotency.complete(session, realm_id=realm_id, scope=SCOPE, key=operation_key, status_code=200, body=body)
    return body


def _decide(
    session: Session,
    *,
    realm_id: UUID,
    external_id: str,
    operation_key: str,
    request: PermitRequest,
    now: datetime,
    queue_lag: float | None,
    config: NodeConfig,
    signer: Signer,
) -> dict[str, Any]:
    app_id = applications.find_id(session, realm_id, external_id)
    if app_id is None:
        return _refused(RefusalResult(Refusal.APPLICATION_NOT_FOUND))
    app = applications.lock(session, {app_id})[app_id]
    snapshot = (
        applications.snapshot_of(session, app, app.current_version)[0].model_dump(mode="json")
        if app.current_version > 0
        else None
    )
    facts = ApplicationFacts(
        status=app.status,
        current_version=app.current_version,
        assessed_version=app.assessed_version,
        needs_reassessment=app.needs_reassessment,
        reassessment_cause=app.reassessment_cause,
        version_gap=app.version_gap_since is not None,
        assessment_point=app.assessment_point,
        assessment_outcome=app.assessment_outcome,
        assessment_valid_until=app.assessment_valid_until,
    )
    operation = _operation_facts(session, app_id, snapshot, request, repository.active_holds(session, app_id))
    refusal = check(facts, operation, request, now, queue_lag, config.queue.max_lag_seconds)
    trail = {
        "application_id": str(app_id),
        "external_id": external_id,
        "operation_key": operation_key,
        **asdict(request),
    }
    if refusal is not None:
        audit.append(
            session,
            realm_id,
            "permit.refused",
            {**trail, "refusal": refusal.code.value, "details": refusal.details},
            now,
        )
        return _refused(refusal)

    if app.latest_decision_id is None:
        raise AssertionError("оценённая заявка без решения")
    permit_id = uuid4()
    expires_at = now + timedelta(seconds=config.permits.reserve_ttl_seconds)
    payload = {
        "permit_id": str(permit_id),
        "realm_id": str(realm_id),
        "application_id": external_id,
        "application_version": app.current_version,
        "operation_type": request.operation_type,
        "tranche": request.tranche,
        "operation_key": operation_key,
        "amount_max": request.amount,
        "account": request.account,
        "decision_id": str(app.latest_decision_id),
        "expires_at": expires_at.isoformat(),
    }
    signature = signer.sign(payload)
    session.add(
        Permit(
            id=permit_id,
            realm_id=realm_id,
            application_id=app_id,
            operation_type=request.operation_type,
            tranche=request.tranche,
            operation_key=operation_key,
            application_version=app.current_version,
            decision_id=app.latest_decision_id,
            amount=request.amount,
            account=request.account,
            status=RESERVED,
            payload=payload,
            signature=signature,
            key_id=signer.key_id,
            reserved_at=now,
            expires_at=expires_at,
            finished_at=None,
        )
    )
    session.flush()
    audit.append(
        session,
        realm_id,
        "permit.reserved",
        {**trail, "permit_id": str(permit_id), "expires_at": expires_at.isoformat()},
        now,
    )
    outbox.enqueue(session, config.outbox, realm_id, "permit.reserved", payload, now)
    return {
        "granted": True,
        "permit": {"payload": payload, "signature": signature, "key_id": signer.key_id},
        "refusal": None,
    }


def _finish(session: Session, permit: Permit, status: str, kind: str, config: NodeConfig, now: datetime) -> None:
    permit.status = status
    permit.finished_at = now
    event = {"permit_id": str(permit.id), "operation_key": permit.operation_key, "status": status}
    audit.append(session, permit.realm_id, kind, event, now)
    outbox.enqueue(session, config.outbox, permit.realm_id, "permit.finished", event, now)


def record_outcome(
    session: Session, *, realm_id: UUID, operation_key: str, status: str, config: NodeConfig, now: datetime
) -> Permit:
    permit = repository.by_operation_key(session, realm_id, operation_key, lock=True)
    if permit is None:
        raise NotFoundError("permit_not_found", "Разрешение с таким ключом операции не выдавалось")
    target = next_status(permit.status, status)
    if target is None:
        raise ConflictError(
            "outcome_conflict",
            f"Итог операции уже другой: {permit.status}",
            {"current": permit.status, "reported": status},
        )
    if target != permit.status:
        _finish(session, permit, target, "permit.outcome", config, now)
    return permit


def expire_reserved(session: Session, now: datetime) -> int:
    """Резерв без итога в срок → «неизвестно»: новое разрешение на эту операцию не выдаётся до сверки."""
    expired = repository.expired_reserved(session, now)
    for permit in expired:
        permit.status = UNKNOWN
        audit.append(
            session,
            permit.realm_id,
            "permit.unknown",
            {"permit_id": str(permit.id), "operation_key": permit.operation_key},
            now,
        )
    return len(expired)


def unknown_operations(session: Session, limit: int) -> list[tuple[UUID, str]]:
    """Операции со статусом «неизвестно» для сверки с АБС: (контур, ключ операции)."""
    return [(p.realm_id, p.operation_key) for p in repository.unknown(session, limit)]


def settle_unknown(
    session: Session, realm_id: UUID, operation_key: str, executed: bool, config: NodeConfig, now: datetime
) -> bool:
    """Итог сверки с АБС. Если за время сверки итог уже пришёл сам — ничего не меняет."""
    permit = repository.by_operation_key(session, realm_id, operation_key, lock=True)
    if permit is None or permit.status != UNKNOWN:
        return False
    _finish(session, permit, "executed" if executed else NOT_EXECUTED, "permit.reconciled", config, now)
    return True


def place_hold(
    session: Session,
    *,
    realm_id: UUID,
    application_id: UUID,
    decision_id: UUID,
    required_check: str,
    basis: list[dict[str, Any]],
    config: NodeConfig,
    now: datetime,
) -> Hold | None:
    """Удержание на заявку. Если такое же уже действует — не дублируется."""
    if any(h.required_check == required_check for h in repository.active_holds(session, application_id)):
        return None
    hold = Hold(
        id=uuid4(),
        realm_id=realm_id,
        application_id=application_id,
        decision_id=decision_id,
        required_check=required_check,
        basis=basis,
        status="active",
        created_at=now,
        released_at=None,
        released_by=None,
    )
    session.add(hold)
    event = {
        "hold_id": str(hold.id),
        "application_id": str(application_id),
        "decision_id": str(decision_id),
        "required_check": required_check,
        "basis": basis,
    }
    audit.append(session, realm_id, "hold.placed", event, now)
    outbox.enqueue(session, config.outbox, realm_id, "hold.placed", event, now)
    return hold


def active_holds(session: Session, application_id: UUID) -> list[Hold]:
    return repository.active_holds(session, application_id)


def applications_with_live_permits(session: Session, application_ids: list[UUID]) -> int:
    return repository.count_live(session, application_ids)


def counts_by_status(session: Session, realm_id: UUID) -> dict[str, int]:
    return repository.counts_by_status(session, realm_id)
