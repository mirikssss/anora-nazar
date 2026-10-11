"""Роутер модуля: состояние заявки для сотрудника — версия, оценка, пометка, удержания."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from node.deps import Ctx, Realm, require_permission
from node.modules.applications import service
from node.modules.identity.domain import StaffPrincipal
from node.modules.permits import service as permits

router = APIRouter(prefix="/v1/applications", tags=["Заявки"])
Viewer = Annotated[StaffPrincipal, Depends(require_permission("decisions.view"))]


class HoldView(BaseModel):
    hold_id: UUID
    required_check: str
    basis: list[dict[str, Any]]
    created_at: datetime


class ApplicationView(BaseModel):
    application_id: str
    channel: str
    status: str
    current_version: int
    assessed_version: int | None
    latest_decision_id: UUID | None
    assessment_level: str | None
    assessment_outcome: str | None
    assessment_valid_until: datetime | None
    needs_reassessment: bool
    reassessment_cause: dict[str, Any] | None
    version_gap: bool
    holds: list[HoldView]


@router.get("/{application_id}", response_model=ApplicationView)
def get_application(application_id: str, ctx: Ctx, realm: Realm, _: Viewer) -> ApplicationView:
    with ctx.db.transaction() as session:
        app = service.get_visible(session, realm.visible_ids, application_id)
        holds = permits.active_holds(session, app.id)
        return ApplicationView(
            application_id=app.external_id,
            channel=app.channel,
            status=app.status,
            current_version=app.current_version,
            assessed_version=app.assessed_version,
            latest_decision_id=app.latest_decision_id,
            assessment_level=app.assessment_level,
            assessment_outcome=app.assessment_outcome,
            assessment_valid_until=app.assessment_valid_until,
            needs_reassessment=app.needs_reassessment,
            reassessment_cause=app.reassessment_cause,
            version_gap=app.version_gap_since is not None,
            holds=[
                HoldView(hold_id=h.id, required_check=h.required_check, basis=h.basis, created_at=h.created_at)
                for h in holds
            ],
        )
