"""Роутер модуля: версии моделей в контуре, запрос выпуска и подтверждение вторым подписантом."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from node.deps import Ctx, Realm, require_permission
from node.modules.identity.domain import StaffPrincipal
from node.modules.scoring import service
from node.modules.scoring.models import ModelRelease
from node.modules.scoring.schemas import ModelVersionOut, ReleaseOut
from node.modules.scoring.training import release

router = APIRouter(prefix="/v1/models", tags=["Модели"])
Viewer = Annotated[StaffPrincipal, Depends(require_permission("quality.view"))]
Promoter = Annotated[StaffPrincipal, Depends(require_permission("models.promote"))]


def _release_out(r: ModelRelease) -> ReleaseOut:
    return ReleaseOut(
        release_id=r.id,
        model_version_id=r.model_version_id,
        model_name=r.model_name,
        requested_by=r.requested_by,
        requested_at=r.requested_at,
        approved_by=r.approved_by,
        approved_at=r.approved_at,
    )


@router.get("", response_model=list[ModelVersionOut])
def list_versions(ctx: Ctx, realm: Realm, _: Viewer) -> list[ModelVersionOut]:
    with ctx.db.transaction() as session:
        return [
            ModelVersionOut(
                model_version_id=v.id,
                name=v.name,
                typology=v.typology,
                points=v.points,
                feature_set_version=v.feature_set_version,
                created_at=v.created_at,
                status=status,
                metrics=v.metrics,
            )
            for v, status in service.versions_with_status(session, realm)
        ]


@router.post("/{model_id}/releases", response_model=ReleaseOut, status_code=201)
def request_release(model_id: UUID, ctx: Ctx, realm: Realm, staff: Promoter) -> ReleaseOut:
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        return _release_out(release.request(session, realm.id, model_id, staff.user_code, now))


@router.post("/releases/{release_id}/approval", response_model=ReleaseOut)
def approve_release(release_id: UUID, ctx: Ctx, realm: Realm, staff: Promoter) -> ReleaseOut:
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        return _release_out(release.approve(session, realm.id, release_id, staff.user_code, now))
