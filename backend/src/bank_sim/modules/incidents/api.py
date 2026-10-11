"""Роутер модуля: жалоба клиента или документ органа по заявкам; лента песочницы."""

from fastapi import APIRouter

from bank_sim.deps import Ctx, Realm
from bank_sim.modules.incidents import service
from bank_sim.modules.incidents.schemas import IncidentOut
from bank_sim.modules.outbox import service as outbox
from shared.contracts.facts import IncidentRecorded

router = APIRouter(prefix="/v1/incidents", tags=["Жалобы и документы органов"])


@router.post("", response_model=IncidentOut, status_code=201)
def create(body: IncidentRecorded, ctx: Ctx, realm: Realm) -> IncidentOut:
    """Тело — контракт факта incident.recorded: вид, типология, итог, заявки, ключ дела."""
    with ctx.db.transaction() as session:
        incident = IncidentOut.model_validate(service.record(session, realm, body, ctx.clock.now()))
    outbox.flush_realm(ctx, realm)
    return incident


@router.get("", response_model=list[IncidentOut])
def list_incidents(ctx: Ctx, realm: Realm) -> list[IncidentOut]:
    with ctx.db.transaction() as session:
        return [IncidentOut.model_validate(i) for i in service.list_for_realm(session, realm)]
