"""Роутер модуля: справочники программ для форм и сценариев, акты приёмки."""

from typing import Annotated

from fastapi import APIRouter, Query

from bank_sim.deps import Ctx, Realm
from bank_sim.modules.outbox import service as outbox
from bank_sim.modules.program_platform import service
from bank_sim.modules.program_platform.models import AcceptanceActRecord
from bank_sim.modules.program_platform.schemas import ActIn, ActOut, HelperOut, SupplierOut

router = APIRouter(prefix="/v1/program", tags=["Платформа программ"])
District = Annotated[str | None, Query(min_length=1, max_length=128)]


def _act(act: AcceptanceActRecord) -> ActOut:
    return ActOut(
        act_id=act.id,
        application_id=act.application_id,
        signer_id=act.signer_id,
        signer_role=act.signer_role,
        signed_on=act.signed_on,
        invoice_amount=act.invoice_amount,
        created_at=act.created_at,
    )


@router.get("/helpers", response_model=list[HelperOut])
def list_helpers(ctx: Ctx, district: District = None) -> list[HelperOut]:
    with ctx.db.transaction() as session:
        return [HelperOut.model_validate(h) for h in service.helpers(session, district)]


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(
    ctx: Ctx, district: District = None, category: Annotated[str | None, Query(min_length=1, max_length=64)] = None
) -> list[SupplierOut]:
    with ctx.db.transaction() as session:
        return [SupplierOut.model_validate(s) for s in service.suppliers(session, district, category)]


@router.post("/acts", response_model=ActOut, status_code=201)
def create_act(body: ActIn, ctx: Ctx, realm: Realm) -> ActOut:
    """Акт уходит в узел сразу: АБС запросит оплату поставщику по нему прямо перед проводкой."""
    with ctx.db.transaction() as session:
        act = _act(service.create_act(session, realm, body, ctx.clock.now()))
    outbox.flush_realm(ctx, realm)
    return act


@router.get("/acts", response_model=list[ActOut])
def list_acts(
    ctx: Ctx, realm: Realm, application_id: Annotated[str | None, Query(min_length=1, max_length=32)] = None
) -> list[ActOut]:
    with ctx.db.transaction() as session:
        return [_act(a) for a in service.acts(session, realm, application_id)]
