"""Схемы входа и выхода API модуля."""

from typing import Any

from pydantic import BaseModel, Field


class Flags(BaseModel):
    lose_outcome: bool = Field(description="АБС проводит операцию, но итог в узел не доходит")
    node_unavailable: bool = Field(description="Узел недоступен: заявки ждут, деньги не двигаются")
    queue_lag: bool = Field(description="Очередь событий в узел стоит")


class FlagsPatch(BaseModel):
    lose_outcome: bool | None = None
    node_unavailable: bool | None = None
    queue_lag: bool | None = None


class RepeatIn(BaseModel):
    operation_key: str = Field(min_length=1, max_length=128)
    amount: int = Field(gt=0, description="Другая сумма для того же ключа операции")


class RepeatOut(BaseModel):
    node_status_code: int
    node_response: dict[str, Any]
