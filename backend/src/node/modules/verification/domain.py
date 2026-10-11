"""Чистая логика проверки намерения: конфигурация вопросов и итог ответов."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from shared.contracts.facts import IntentAnswer


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AnswerOption(_Frozen):
    code: str
    alarming: bool


class Question(_Frozen):
    code: str
    answers: list[AnswerOption] = Field(min_length=2)


class VerificationConfig(_Frozen):
    version: str
    questions: list[Question] = Field(min_length=1)
    check: str
    escalation: str


class Verdict(StrEnum):
    CONFIRMED = "confirmed"  # все ответы спокойные — проверка намерения закрыта
    ALARMING = "alarming"  # тревожный ответ — пауза до звонка аналитика
    INCOMPLETE = "incomplete"  # ответили не на все вопросы или неизвестным вариантом


def verdict(config: VerificationConfig, answers: list[IntentAnswer]) -> Verdict:
    given = {a.question: a.answer for a in answers}
    alarming = False
    for question in config.questions:
        option = next((o for o in question.answers if o.code == given.get(question.code)), None)
        if option is None:
            return Verdict.INCOMPLETE
        alarming = alarming or option.alarming
    return Verdict.ALARMING if alarming else Verdict.CONFIRMED
