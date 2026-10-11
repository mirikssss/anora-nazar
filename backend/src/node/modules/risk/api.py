"""Роутер модуля: обзор риск-менеджера."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from node.deps import Ctx, Realm, require_permission
from node.modules.identity.domain import StaffPrincipal
from node.modules.risk import service

router = APIRouter(prefix="/v1/risk", tags=["Обзор риска"])
Viewer = Annotated[StaffPrincipal, Depends(require_permission("quality.view"))]


class DayLevels(BaseModel):
    day: date
    green: int
    yellow: int
    red: int
    stopped: int


class DriftOut(BaseModel):
    feature: str
    psi: float | None
    reference: int
    recent: int


class RiskOverviewOut(BaseModel):
    latest: datetime | None
    levels: list[DayLevels]
    queues: dict[str, int]
    drift: list[DriftOut]


@router.get("/overview", response_model=RiskOverviewOut)
def overview(ctx: Ctx, realm: Realm, _: Viewer) -> RiskOverviewOut:
    with ctx.db.transaction() as session:
        return RiskOverviewOut.model_validate(service.overview(session, realm, ctx.config.risk))
