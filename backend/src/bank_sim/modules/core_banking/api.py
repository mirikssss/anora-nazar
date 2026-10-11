"""Роутер модуля: исполнить операцию по разрешению узла; статус операции для сверки узлом."""

from fastapi import APIRouter

from bank_sim.deps import Ctx, NodeRealm, Realm
from bank_sim.modules.core_banking import service
from bank_sim.modules.core_banking.models import Operation
from bank_sim.modules.core_banking.schemas import OperationIn, OperationOut, OperationStatusOut

router = APIRouter(tags=["АБС"])


def _out(op: Operation) -> OperationOut:
    return OperationOut(
        operation_key=op.operation_key,
        application_id=op.application_external_id,
        application_version=op.application_version,
        operation_type=op.operation_type,
        tranche=op.tranche,
        amount=op.amount,
        account=op.account,
        status=op.status,
        permit=op.permit,
        refusal=op.refusal,
        outcome_reported=op.outcome_reported,
        created_at=op.created_at,
        updated_at=op.updated_at,
    )


@router.post("/v1/core-banking/operations", response_model=OperationOut, status_code=201)
def execute(body: OperationIn, ctx: Ctx, realm: Realm) -> OperationOut:
    return _out(service.execute(ctx, realm, body))


@router.get("/v1/core-banking/operations", response_model=list[OperationOut])
def list_operations(ctx: Ctx, realm: Realm) -> list[OperationOut]:
    return [_out(op) for op in service.list_for_realm(ctx, realm)]


@router.get("/v1/core-banking/operations/{operation_key}", response_model=OperationOut)
def get_operation(operation_key: str, ctx: Ctx, realm: Realm) -> OperationOut:
    return _out(service.get(ctx, realm, operation_key))


@router.get("/v1/node/operations/{operation_key}", response_model=OperationStatusOut)
def status_for_node(operation_key: str, ctx: Ctx, realm: NodeRealm) -> OperationStatusOut:
    return OperationStatusOut(status=service.status_for_node(ctx, realm, operation_key))
