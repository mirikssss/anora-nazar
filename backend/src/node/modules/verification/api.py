"""Роутер модуля: вопросы проверки намерения для приложения банка (тексты — в каталоге текстов по кодам)."""

from fastapi import APIRouter
from pydantic import BaseModel

from node.deps import Ctx
from node.modules.verification import service

router = APIRouter(prefix="/v1/verification", tags=["Проверка намерения"])


class AnswerOut(BaseModel):
    code: str


class QuestionOut(BaseModel):
    code: str
    answers: list[AnswerOut]


class QuestionsOut(BaseModel):
    version: str
    questions: list[QuestionOut]


@router.get("/questions", response_model=QuestionsOut)
def questions(ctx: Ctx) -> QuestionsOut:
    return QuestionsOut.model_validate(service.questions(ctx.verification_config))
