"""Схемы входа и выхода API модуля."""

from pydantic import BaseModel

from shared.contracts.network import OutageIn

__all__ = ["OutageIn", "OutageOut"]


class OutageOut(BaseModel):
    active: bool
