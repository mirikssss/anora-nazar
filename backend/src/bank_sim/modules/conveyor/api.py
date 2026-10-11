"""Роутер модуля: новая заявка (свой ввод проверяющего), оценка, новая версия, отмена; снимок для узла."""

from fastapi import APIRouter

from bank_sim.deps import Ctx, NodeRealm, Realm
from bank_sim.modules.conveyor import service
from bank_sim.modules.conveyor.models import ConveyorApplication
from bank_sim.modules.conveyor.schemas import ApplicationChange, ApplicationDraft, ApplicationOut, SnapshotOut

router = APIRouter(tags=["Конвейер"])


def _out(app: ConveyorApplication) -> ApplicationOut:
    return ApplicationOut(
        id=app.external_id,
        channel=app.channel,
        version=app.version,
        status=app.status,
        node_state=app.node_state,
        snapshot=app.snapshot,
        last_decision=app.last_decision,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


@router.post("/v1/conveyor/applications", response_model=ApplicationOut, status_code=201)
def create(body: ApplicationDraft, ctx: Ctx, realm: Realm) -> ApplicationOut:
    """Заявка проходит обязательные шаги, затем конвейер спрашивает оценку узла (Т1 или Т4)."""
    with ctx.db.transaction() as session:
        external_id = service.create(session, realm, body, ctx.clock.now()).external_id
    return _out(service.assess(ctx, realm, external_id))


@router.post("/v1/conveyor/applications/{application_id}/assessments", response_model=ApplicationOut)
def reassess(application_id: str, ctx: Ctx, realm: Realm) -> ApplicationOut:
    return _out(service.assess(ctx, realm, application_id))


@router.patch("/v1/conveyor/applications/{application_id}", response_model=ApplicationOut)
def change(application_id: str, body: ApplicationChange, ctx: Ctx, realm: Realm) -> ApplicationOut:
    with ctx.db.transaction() as session:
        return _out(service.change(session, realm, application_id, body, ctx.clock.now()))


@router.post("/v1/conveyor/applications/{application_id}/cancel", response_model=ApplicationOut)
def cancel(application_id: str, ctx: Ctx, realm: Realm) -> ApplicationOut:
    with ctx.db.transaction() as session:
        return _out(service.cancel(session, realm, application_id, ctx.clock.now()))


@router.get("/v1/conveyor/applications", response_model=list[ApplicationOut])
def list_applications(ctx: Ctx, realm: Realm) -> list[ApplicationOut]:
    with ctx.db.transaction() as session:
        return [_out(a) for a in service.list_for_realm(session, realm)]


@router.get("/v1/conveyor/applications/{application_id}", response_model=ApplicationOut)
def get_application(application_id: str, ctx: Ctx, realm: Realm) -> ApplicationOut:
    with ctx.db.transaction() as session:
        return _out(service.get(session, realm, application_id))


@router.get("/v1/node/applications/{application_id}/snapshot", response_model=SnapshotOut)
def snapshot_for_node(application_id: str, ctx: Ctx, realm: NodeRealm) -> SnapshotOut:
    """Актуальный снимок по запросу узла, когда он ждёт пропущенную версию."""
    with ctx.db.transaction() as session:
        app = service.get(session, realm, application_id)
        return SnapshotOut(version=app.version, snapshot=app.snapshot)
