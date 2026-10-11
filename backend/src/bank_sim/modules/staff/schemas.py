"""Схемы входа и выхода API модуля."""

from pydantic import BaseModel


class EmployeeOut(BaseModel):
    id: str
    display_name: str
    role: str


class BranchOut(BaseModel):
    id: str
    name: str
    district: str
    employees: list[EmployeeOut]
