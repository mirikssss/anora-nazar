"""Схемы входа и выхода API модуля."""

from uuid import UUID

from pydantic import BaseModel


class SandboxCreate(BaseModel):
    id: UUID


class RealmOut(BaseModel):
    id: UUID
    is_sandbox: bool
    world_id: UUID
