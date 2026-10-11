"""Роутер модуля: персоны, онлайн-заявка из приложения, экран заявки, ответы, «Меня просят», отмена."""

from typing import Annotated

from fastapi import APIRouter, Query

from bank_sim.deps import Ctx, Realm
from bank_sim.modules.borrower_app import service
from bank_sim.modules.borrower_app.schemas import (
    BorrowerApplicationIn,
    BorrowerScreenOut,
    IntentAnswersIn,
    PersonaOut,
)

router = APIRouter(prefix="/v1/borrower", tags=["Приложение заёмщика"])


@router.get("/personas", response_model=list[PersonaOut])
def list_personas(ctx: Ctx) -> list[PersonaOut]:
    return service.personas_view(ctx)


@router.post("/applications", response_model=BorrowerScreenOut, status_code=201)
def create(body: BorrowerApplicationIn, ctx: Ctx, realm: Realm) -> BorrowerScreenOut:
    """Онлайн-заявка персоны; в ответе — экран по решению узла (Т1)."""
    return service.create(ctx, realm, body)


@router.get("/applications", response_model=list[BorrowerScreenOut])
def list_applications(
    ctx: Ctx, realm: Realm, persona_code: Annotated[str | None, Query(min_length=1, max_length=32)] = None
) -> list[BorrowerScreenOut]:
    return service.list_views(ctx, realm, persona_code)


@router.get("/applications/{application_id}", response_model=BorrowerScreenOut)
def get_application(application_id: str, ctx: Ctx, realm: Realm) -> BorrowerScreenOut:
    return service.view(ctx, realm, application_id)


@router.post("/applications/{application_id}/intent-answers", response_model=BorrowerScreenOut)
def answer_intent(application_id: str, body: IntentAnswersIn, ctx: Ctx, realm: Realm) -> BorrowerScreenOut:
    return service.answer_intent(ctx, realm, application_id, body)


@router.post("/applications/{application_id}/pressure", response_model=BorrowerScreenOut)
def report_pressure(application_id: str, ctx: Ctx, realm: Realm) -> BorrowerScreenOut:
    return service.report_pressure(ctx, realm, application_id)


@router.post("/applications/{application_id}/cancel", response_model=BorrowerScreenOut)
def cancel(application_id: str, ctx: Ctx, realm: Realm) -> BorrowerScreenOut:
    return service.cancel(ctx, realm, application_id)
