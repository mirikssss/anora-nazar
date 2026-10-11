"""Схемы входа и выхода API модуля."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    outcome: Literal["marked", "ignored", "duplicate"]


class NetworkOverviewOut(BaseModel):
    """Страница «Сеть кредиторов»: переключатель из политики и счётчики оператора по своему контуру."""

    enabled: bool = Field(description="Сеть включена действующей политикой контура")
    policy_version: str
    contract: str
    configured: bool = Field(description="Адрес оператора задан в окружении узла")
    available: bool = Field(description="Оператор ответил сейчас")
    toggle_path: str = Field(description="Путь переключателя в предложении порогов со вторым подписантом")
    rules: list[dict[str, Any]]
    operator: dict[str, Any] | None = Field(description="Счётчики оператора по кредитору и контуру; null — не ответил")
    decisions: dict[str, int] = Field(description="Решения контура по статусу ответа сети")
    notifications: int
