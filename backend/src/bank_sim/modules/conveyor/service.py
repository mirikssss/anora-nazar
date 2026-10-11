"""Конвейер: заявка, обязательные шаги № 3759, вызовы Т1/Т4, новые версии и отмена."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from bank_sim.context import BankContext
from bank_sim.modules.conveyor import repository
from bank_sim.modules.conveyor.domain import apply_change, build_snapshot
from bank_sim.modules.conveyor.models import ConveyorApplication
from bank_sim.modules.conveyor.schemas import ApplicationChange, ApplicationDraft
from bank_sim.modules.failures import service as failures
from bank_sim.modules.outbox import service as outbox
from bank_sim.modules.sources import service as sources
from bank_sim.modules.staff import service as staff
from shared.errors import ConflictError, NotFoundError, UpstreamUnavailableError, ValidationFailedError

SOURCE = "bank-sim.conveyor"
POINT = {"online": "T1", "program": "T4"}


def _snapshot(session: Session, realm_id: UUID, draft: ApplicationDraft, now: datetime) -> dict[str, Any]:
    pinfl = draft.applicant.pinfl
    snapshot = build_snapshot(
        draft, sources.self_ban_status(session, realm_id, pinfl), sources.bureau_status(session, realm_id, pinfl, now)
    )
    return snapshot.model_dump(mode="json")


def get(session: Session, realm_id: UUID, external_id: str, *, lock: bool = False) -> ConveyorApplication:
    app = repository.by_external(session, realm_id, external_id, lock=lock)
    if app is None:
        raise NotFoundError("application_not_found", "Заявка не найдена")
    return app


def create(session: Session, realm_id: UUID, draft: ApplicationDraft, now: datetime) -> ConveyorApplication:
    staff.ensure_assignment(session, draft.branch_id, draft.employee_id)
    app = ConveyorApplication(
        id=uuid4(),
        realm_id=realm_id,
        external_id=f"APP-{uuid4().hex[:8].upper()}",
        channel=draft.channel,
        version=1,
        draft=draft.model_dump(mode="json"),
        snapshot=_snapshot(session, realm_id, draft, now),
        status="pending_assessment",
        last_decision=None,
        node_state=None,
        created_at=now,
        updated_at=now,
    )
    repository.add(session, app)
    return app


def change(
    session: Session, realm_id: UUID, external_id: str, patch: ApplicationChange, now: datetime
) -> ConveyorApplication:
    app = get(session, realm_id, external_id, lock=True)
    if app.status == "cancelled":
        raise ConflictError("application_cancelled", "Заявка отменена")
    try:
        draft = apply_change(app.draft, patch)
    except ValueError as exc:
        raise ValidationFailedError("invalid_change", str(exc)) from exc
    app.version += 1
    app.draft = draft.model_dump(mode="json")
    app.snapshot = _snapshot(session, realm_id, draft, now)
    app.status = "pending_assessment"
    app.updated_at = now
    outbox.emit(
        session,
        realm_id,
        source=SOURCE,
        type_="application.version",
        entity_type="application",
        entity_id=app.external_id,
        entity_version=app.version,
        payload={"snapshot": app.snapshot},
        occurred_at=now,
    )
    return app


def cancel(session: Session, realm_id: UUID, external_id: str, now: datetime) -> ConveyorApplication:
    app = get(session, realm_id, external_id, lock=True)
    if app.status != "cancelled":
        app.status = "cancelled"
        app.updated_at = now
        outbox.emit(
            session,
            realm_id,
            source=SOURCE,
            type_="application.cancelled",
            entity_type="application",
            entity_id=app.external_id,
            entity_version=None,
            payload={},
            occurred_at=now,
        )
    return app


def assess(ctx: BankContext, realm_id: UUID, external_id: str) -> ConveyorApplication:
    """Т1/Т4: запрос оценки текущей версии. Узел недоступен — заявка ждёт, деньги не двигаются."""
    with ctx.db.transaction() as session:
        app = get(session, realm_id, external_id)
        if app.status == "cancelled":
            raise ConflictError("application_cancelled", "Заявка отменена")
        flags = failures.flags(session, realm_id)
        version = app.version
        body = {
            "point": POINT[app.channel],
            "application_id": app.external_id,
            "application_version": version,
            "occurred_at": app.updated_at.isoformat(),
            "snapshot": app.snapshot,
        }
    try:
        failures.ensure_node_reachable(flags)
        decision = ctx.node.assess(realm_id, body, str(uuid4()))
    except UpstreamUnavailableError:
        _record(ctx, realm_id, external_id, version, "waiting_node", None)
        raise
    status = "stopped_by_norm" if decision["outcome"] == "stopped_by_norm" else "assessed"
    return _record(ctx, realm_id, external_id, version, status, decision)


def _record(
    ctx: BankContext, realm_id: UUID, external_id: str, version: int, status: str, decision: dict[str, Any] | None
) -> ConveyorApplication:
    """Итог оценки ложится на заявку, только если за время вызова не появилась новая версия."""
    with ctx.db.transaction() as session:
        app = get(session, realm_id, external_id, lock=True)
        if app.version == version and app.status != "cancelled":
            app.status = status
            if decision is not None:
                app.last_decision = decision
                app.node_state = None
            app.updated_at = ctx.clock.now()
        return app


def note_reassessment_required(session: Session, realm_id: UUID, external_id: str, now: datetime) -> None:
    app = repository.by_external(session, realm_id, external_id, lock=True)
    if app is not None:
        app.node_state = "reassessment_required"
        app.updated_at = now


def list_for_realm(session: Session, realm_id: UUID) -> list[ConveyorApplication]:
    return repository.list_for_realm(session, realm_id)


def operation_terms(app: ConveyorApplication, operation_type: str) -> tuple[int, str]:
    """Сумма и счёт операции — из текущей версии заявки, как их взяла бы АБС."""
    if operation_type == "disbursement":
        if app.channel != "online":
            raise ValidationFailedError("wrong_operation", "Зачисление — только для онлайн-заявки")
        return int(app.snapshot["loan"]["amount"]), str(app.snapshot["disbursement_account"])
    if app.channel != "program":
        raise ValidationFailedError("wrong_operation", "Оплата поставщику — только для программной заявки")
    program = app.snapshot["program"]
    return int(program["unit_price"]) * int(program["quantity"]), str(program["supplier_account"])
