"""Роутер модуля: каталог текстов по аудитории и языку. Публичный: персональных данных в нём нет."""

from typing import Annotated

from fastapi import APIRouter, Query

from node.deps import Ctx
from node.modules.texts import service
from node.modules.texts.domain import Audience
from node.modules.texts.schemas import ClientTextsOut, StaffTextsOut, TextsOut

router = APIRouter(prefix="/v1/texts", tags=["Тексты"])


@router.get("", response_model=TextsOut)
def texts(
    ctx: Ctx,
    audience: Annotated[Audience, Query(description="staff — сотрудник банка или узла; client — заёмщик")],
    lang: Annotated[str | None, Query(pattern=r"^[a-z]{2}$", description="Язык; по умолчанию — язык каталога")] = None,
) -> StaffTextsOut | ClientTextsOut:
    return service.texts(ctx.config.texts.active_catalog, audience, lang)
