"""Схемы входа и выхода API модуля."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from bank_sim.modules.borrower_app.domain import Screen
from shared.contracts.facts import IntentAnswer

MAX_ANSWERS = 20


class PersonaOut(BaseModel):
    code: str
    display_name: str
    age: int
    summary: str
    pinfl: str
    phone: str
    address: str | None
    registration_mahalla: str | None
    card_balance: int


class BorrowerApplicationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_code: str = Field(min_length=1, max_length=32)
    amount: int = Field(gt=0, description="Сумма займа, сум")
    term_months: int = Field(gt=0, le=600)


class IntentAnswersIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[IntentAnswer] = Field(min_length=1, max_length=MAX_ANSWERS)


class AnswerOption(BaseModel):
    code: str


class Question(BaseModel):
    """Вопрос проверки намерения: только коды, тексты по кодам — из узла (каталог текстов для клиента)."""

    code: str
    answers: list[AnswerOption]


class Questions(BaseModel):
    version: str
    questions: list[Question]


class LoanOut(BaseModel):
    amount: int
    term_months: int


class BorrowerScreenOut(BaseModel):
    application_id: str
    persona_code: str | None
    status: str
    screen: Screen
    reason_codes: list[str] = Field(description="Коды причин для текста клиенту — без названий и значений признаков")
    questions: Questions | None = Field(description="Вопросы проверки намерения; null — их сейчас не задают")
    questions_unavailable: bool = Field(description="Проверка намерения нужна, но узел не отдал вопросы")
    intent_answered: bool
    pressure_reported: bool
    can_cancel: bool
    loan: LoanOut
    created_at: datetime
    updated_at: datetime
