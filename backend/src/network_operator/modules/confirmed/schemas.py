"""Схемы входа и выхода API модуля."""

from pydantic import BaseModel, Field

from shared.contracts.network import ConfirmedIn

__all__ = ["ConfirmedIn", "ConfirmedOut"]


class ConfirmedOut(BaseModel):
    accepted: int
    duplicates: int
    conflicts: list[str] = Field(description="result_id, пришедшие повторно с другим содержимым")
