"""Роутер модуля: Т2 и Т5 — разрешение на операцию прямо перед проводкой; итог исполнения."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from node.deps import Ctx, IdempotencyKey, Realm, require_scope
from node.modules.identity.domain import SystemPrincipal
from node.modules.ingest import service as ingest
from node.modules.permits import service
from node.modules.permits.domain import PermitRequest
from node.modules.permits.schemas import OutcomeIn, PermitIn, PermitOut, PermitStatusOut

router = APIRouter(prefix="/v1/permits", tags=["Разрешения"])
CoreBanking = Annotated[SystemPrincipal, Depends(require_scope("permits"))]


@router.post("", response_model=PermitOut)
def request_permit(body: PermitIn, ctx: Ctx, realm: Realm, key: IdempotencyKey, _: CoreBanking) -> PermitOut:
    now = ctx.clock.now()
    request = PermitRequest(
        application_version=body.application_version,
        operation_type=body.operation_type,
        tranche=body.tranche,
        amount=body.amount,
        account=body.account,
    )

    def work(session: Session) -> dict[str, object]:
        lag = ingest.queue_lag_seconds(session, realm.id, ctx.config.queue.watched_producers, now)
        return service.request_permit(
            session,
            realm_id=realm.id,
            external_id=body.application_id,
            operation_key=key,
            request=request,
            now=now,
            queue_lag=lag,
            config=ctx.config,
            signer=ctx.signer,
            idempotency=ctx.idempotency,
        )

    return PermitOut.model_validate(ctx.db.run(work))


@router.post("/outcomes", response_model=PermitStatusOut)
def record_outcome(body: OutcomeIn, ctx: Ctx, realm: Realm, _: CoreBanking) -> PermitStatusOut:
    now = ctx.clock.now()

    def work(session: Session) -> PermitStatusOut:
        permit = service.record_outcome(
            session, realm_id=realm.id, operation_key=body.operation_key, status=body.status, config=ctx.config, now=now
        )
        return PermitStatusOut(
            operation_key=permit.operation_key,
            status=permit.status,
            application_id=str(permit.payload["application_id"]),
            operation_type=permit.operation_type,
            tranche=permit.tranche,
        )

    return ctx.db.run(work)
