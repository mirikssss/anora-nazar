"""Схемы входа и выхода API модуля."""

from typing import Literal

from pydantic import BaseModel, Field


class SelfBanIn(BaseModel):
    pinfl: str = Field(pattern=r"^\d{14}$")
    status: Literal["active", "lifted"]


class RegistryOut(BaseModel):
    pinfl: str
    self_ban: Literal["active", "none"]
    bureau: Literal["free", "blocked"]
