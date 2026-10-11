"""Схемы входа и выхода API модуля."""

from pydantic import BaseModel, Field


class DemoLoginIn(BaseModel):
    user_code: str = Field(min_length=1, max_length=64)


class StaffUserOut(BaseModel):
    code: str
    display_name: str
    division: str


class StaffRoleOut(BaseModel):
    code: str
    title: str
    home_path: str
    summary: str
    permissions: list[str]
    restrictions: list[str]
    users: list[StaffUserOut]


class MeOut(BaseModel):
    user_code: str
    role_code: str
    display_name: str
    division: str
    permissions: list[str]


class DemoLoginOut(BaseModel):
    token: str
    me: MeOut
