"""Роутер модуля: последний отчёт качества моделей для риск-менеджера."""

from typing import Annotated

from fastapi import APIRouter, Depends

from node.deps import Ctx, Realm, require_permission
from node.modules.identity.domain import StaffPrincipal
from node.modules.quality import service
from node.modules.quality.schemas import QualityReportOut

router = APIRouter(prefix="/v1/quality", tags=["Качество моделей"])
Viewer = Annotated[StaffPrincipal, Depends(require_permission("quality.view"))]


@router.get("/reports/latest", response_model=QualityReportOut)
def latest(ctx: Ctx, realm: Realm, _: Viewer) -> QualityReportOut:
    with ctx.db.transaction() as session:
        row = service.latest(session, realm)
        return QualityReportOut(report_id=row.id, created_at=row.created_at, report=row.report)
