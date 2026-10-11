"""Схемы входа и выхода API модуля."""

from pydantic import BaseModel, ConfigDict


class BankRoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    title: str
    home_path: str
    summary: str
    permissions: list[str]
    restrictions: list[str]
