"""Схемы входа и выхода API модуля."""

from pydantic import BaseModel, Field

from shared.contracts.history import HistoryItem


class HistoryBatchIn(BaseModel):
    items: list[HistoryItem] = Field(min_length=1)


class HistoryBatchOut(BaseModel):
    processed: int
    outcomes: dict[str, int]
