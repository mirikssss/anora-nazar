"""АБС: перед проводкой запрашивает разрешение узла, проверяет подпись, проводит, сообщает итог."""

from typing import Any, Literal
from uuid import UUID, uuid4

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from bank_sim.context import BankContext
from bank_sim.modules.conveyor import service as conveyor
from bank_sim.modules.core_banking import repository
from bank_sim.modules.core_banking.models import Operation
from bank_sim.modules.core_banking.schemas import OperationIn
from bank_sim.modules.failures import service as failures
from bank_sim.modules.sources import service as sources
from shared.errors import AppError, ConflictError, NotFoundError, UpstreamUnavailableError

IN_PROGRESS = "in_progress"
EXECUTED = "executed"
NOT_EXECUTED = "not_executed"
REFUSED = "refused"
WAITING_NODE = "waiting_node"
NodeStatus = Literal["executed", "not_executed", "in_progress"]


def _permit_body(op: Operation) -> dict[str, Any]:
    return {
        "application_id": op.application_external_id,
        "application_version": op.application_version,
        "operation_type": op.operation_type,
        "tranche": op.tranche,
        "amount": op.amount,
        "account": op.account,
    }


def _finish(ctx: BankContext, realm_id: UUID, key: str, **changes: Any) -> Operation:
    with ctx.db.transaction() as session:
        op = repository.get(session, realm_id, key, lock=True)
        if op is None:
            raise NotFoundError("operation_not_found", "Операция не найдена")
        for field, value in changes.items():
            setattr(op, field, value)
        op.updated_at = ctx.clock.now()
        return op


def _permit_is_genuine(ctx: BankContext, permit: dict[str, Any], op: Operation) -> bool:
    """АБС проверяет подпись узла и что разрешение выдано именно на эту операцию."""
    payload = permit["payload"]
    return (
        ctx.node_verifier.is_valid(payload, permit["signature"])
        and payload["operation_key"] == op.operation_key
        and payload["account"] == op.account
        and int(payload["amount_max"]) >= op.amount
    )


def _start(ctx: BankContext, session: Session, realm_id: UUID, body: OperationIn) -> Operation:
    """Новая попытка или продолжение той, что ждала узел, — с тем же ключом операции (ревью B)."""
    app = conveyor.get(session, realm_id, body.application_id)
    live = repository.live_for_update(session, realm_id, app.id, body.operation_type, body.tranche)
    now = ctx.clock.now()
    if live is not None:
        if live.status == EXECUTED:
            raise ConflictError("already_executed", "Эта операция уже проведена: повторной проводки не будет")
        if live.status == IN_PROGRESS:
            raise ConflictError("operation_in_progress", "Проводка этой операции уже идёт")
        live.status, live.refusal, live.updated_at = IN_PROGRESS, None, now
        return live
    amount, account = conveyor.operation_terms(app, body.operation_type)
    op = Operation(
        operation_key=str(uuid4()),
        realm_id=realm_id,
        application_id=app.id,
        application_external_id=app.external_id,
        application_version=app.version,
        operation_type=body.operation_type,
        tranche=body.tranche,
        amount=amount,
        account=account,
        status=IN_PROGRESS,
        permit=None,
        refusal=None,
        outcome_reported=False,
        created_at=now,
        updated_at=now,
    )
    repository.add(session, op)
    session.flush()
    return op


def execute(ctx: BankContext, realm_id: UUID, body: OperationIn) -> Operation:
    try:
        with ctx.db.transaction() as session:
            op = _start(ctx, session, realm_id, body)
            app = conveyor.get(session, realm_id, body.application_id)
            flags = failures.flags(session, realm_id)
            pinfl = str(app.snapshot["applicant"]["pinfl"])
            key, request_body = op.operation_key, _permit_body(op)
    except IntegrityError as exc:
        raise ConflictError("operation_in_progress", "Проводка этой операции уже идёт") from exc

    try:
        failures.ensure_node_reachable(flags)
        response = ctx.node.request_permit(realm_id, request_body, key)
    except UpstreamUnavailableError as exc:
        return _finish(ctx, realm_id, key, status=WAITING_NODE, refusal={"code": exc.code, "message": exc.message})
    return _settle(ctx, realm_id, key, op, response, pinfl, flags.lose_outcome)


def _settle(
    ctx: BankContext, realm_id: UUID, key: str, op: Operation, response: httpx.Response, pinfl: str, lose_outcome: bool
) -> Operation:
    body = response.json()
    if not response.is_success:
        return _finish(ctx, realm_id, key, status=NOT_EXECUTED, refusal=body.get("error", {}))
    if not body["granted"]:
        return _finish(ctx, realm_id, key, status=REFUSED, refusal=body["refusal"])
    permit = body["permit"]
    if not _permit_is_genuine(ctx, permit, op):
        _report(ctx, realm_id, key, NOT_EXECUTED)
        return _finish(
            ctx,
            realm_id,
            key,
            status=NOT_EXECUTED,
            permit=permit,
            refusal={"code": "permit_not_genuine", "message": "Подпись разрешения не сходится"},
        )

    executed = _finish(ctx, realm_id, key, status=EXECUTED, permit=permit)
    if op.operation_type == "disbursement":
        with ctx.db.transaction() as session:
            sources.lock_after_disbursement(session, realm_id, pinfl, ctx.clock.now(), ctx.config.bureau.lock_hours)
    if lose_outcome:
        return executed
    return _report(ctx, realm_id, key, EXECUTED) or executed


def _report(ctx: BankContext, realm_id: UUID, key: str, status: str) -> Operation | None:
    """Итог проводки — в узел. Не дошёл — узел сам спросит статус по ключу операции."""
    try:
        ctx.node.report_outcome(realm_id, key, status)
    except AppError:
        return None
    return _finish(ctx, realm_id, key, outcome_reported=True)


def status_for_node(ctx: BankContext, realm_id: UUID, key: str) -> NodeStatus:
    with ctx.db.transaction() as session:
        op = repository.get(session, realm_id, key)
        if op is None:
            raise NotFoundError("operation_not_found", "Операции с таким ключом не было")
        if op.status == IN_PROGRESS:
            return "in_progress"
        return "executed" if op.status == EXECUTED else "not_executed"


def get(ctx: BankContext, realm_id: UUID, key: str) -> Operation:
    with ctx.db.transaction() as session:
        op = repository.get(session, realm_id, key)
        if op is None:
            raise NotFoundError("operation_not_found", "Операция не найдена")
        return op


def list_for_realm(ctx: BankContext, realm_id: UUID) -> list[Operation]:
    with ctx.db.transaction() as session:
        return repository.list_for_realm(session, realm_id)


def repeat_with_other_amount(ctx: BankContext, realm_id: UUID, key: str, amount: int) -> httpx.Response:
    """Кнопка сбоя: тот же ключ операции с другой суммой. Узел обязан ответить конфликтом 409."""
    body = {**_permit_body(get(ctx, realm_id, key)), "amount": amount}
    return ctx.node.request_permit(realm_id, body, key)
