"""Чистая логика приложения заёмщика: экран из последнего решения узла, его уведомлений и действий клиента."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Screen = Literal["approved", "intent_check", "pause", "under_review", "stopped", "cancelled"]

CANCELLED_STATUS = "cancelled"
STOPPED_OUTCOME = "stopped_by_norm"
HOLD_PLACED = "hold.placed"
HOLD_RELEASED = "hold.released"


class ScreenRules(BaseModel):
    """Какой экран показывает приложение по проверке удержания; значения — config/bank_sim.yaml."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    by_check: dict[str, Screen] = Field(min_length=1)
    unknown_check: Screen
    priority: list[Screen] = Field(min_length=1)

    @model_validator(mode="after")
    def _ranked(self) -> Self:
        missing = ({*self.by_check.values(), self.unknown_check} | {"approved"}) - set(self.priority)
        if missing:
            raise ValueError(f"В порядке экранов нет: {', '.join(sorted(missing))}")
        return self

    def screen_for(self, check: str) -> Screen:
        return self.by_check.get(check, self.unknown_check)

    def strictest(self, screens: Iterable[Screen]) -> Screen:
        return min(screens, key=self.priority.index)


@dataclass(frozen=True)
class Notice:
    """Уведомление узла по заявке в порядке его outbox."""

    topic: str
    payload: Mapping[str, Any]
    received_at: datetime


@dataclass(frozen=True)
class BorrowerState:
    status: str  # статус заявки у конвейера
    decision: Mapping[str, Any] | None  # последнее решение узла (ответ Т1)
    notices: tuple[Notice, ...]
    intent_answered: bool
    pressure_reported_at: datetime | None


def _hold_story(state: BorrowerState) -> tuple[dict[str, str], bool, list[datetime]]:
    """Действующие удержания (id → проверка), были ли удержания вообще и когда их снимали."""
    holds: dict[str, str] = {}
    decision = state.decision or {}
    for hold in decision.get("holds", []):
        holds[str(hold["hold_id"])] = str(hold["required_check"])
    ever = bool(holds)
    released_at: list[datetime] = []
    for notice in state.notices:
        hold_id = str(notice.payload.get("hold_id", ""))
        if notice.topic == HOLD_PLACED:
            holds[hold_id] = str(notice.payload.get("required_check", ""))
            ever = True
        elif notice.topic == HOLD_RELEASED:
            holds.pop(hold_id, None)
            released_at.append(notice.received_at)
    return holds, ever, released_at


def screen(state: BorrowerState, rules: ScreenRules) -> Screen:
    """Экран заёмщика. Пауза держится, пока удержание не снимет аналитик: из приложения её не снять (Блок 4)."""
    if state.status == CANCELLED_STATUS:
        return "cancelled"
    if state.decision is None:
        return "under_review"
    if state.decision.get("outcome") == STOPPED_OUTCOME:
        return "stopped"

    def shown(check: str) -> Screen:
        """Ответы на проверку намерения отправлены — ждём узел: «на проверке», а не вопросы ещё раз."""
        result = rules.screen_for(check)
        return "under_review" if result == "intent_check" and state.intent_answered else result

    holds, ever, released_at = _hold_story(state)
    candidates = [shown(check) for check in holds.values()]
    pressed = state.pressure_reported_at
    if pressed is not None and not any(moment > pressed for moment in released_at):
        candidates.append("pause")
    if candidates:
        return rules.strictest(candidates)
    if ever:
        return "approved"
    return shown(str(state.decision.get("action", "")))


def reason_codes(decision: Mapping[str, Any] | None) -> list[str]:
    """Коды причин, которые дали уровень, без доказательств: экран называет причину в общем виде (Блок 5)."""
    if decision is None:
        return []
    codes = [str(r["code"]) for r in decision.get("reasons", []) if r.get("level") is not None]
    return list(dict.fromkeys(codes))


def check_answers(questions: Mapping[str, set[str]], answers: list[tuple[str, str]]) -> None:
    """Ответ — на каждый вопрос ровно один, из его вариантов. Иначе ValueError с понятным текстом."""
    asked = [question for question, _ in answers]
    if len(set(asked)) != len(asked):
        raise ValueError("На каждый вопрос — один ответ")
    unknown = [question for question in asked if question not in questions]
    if unknown:
        raise ValueError(f"Таких вопросов нет: {', '.join(unknown)}")
    missing = [question for question in questions if question not in asked]
    if missing:
        raise ValueError(f"Нет ответа на вопросы: {', '.join(missing)}")
    wrong = [question for question, answer in answers if answer not in questions[question]]
    if wrong:
        raise ValueError(f"Неизвестный вариант ответа на вопросы: {', '.join(wrong)}")
