"""Схемы входа и выхода API модуля."""

from uuid import UUID

from pydantic import BaseModel


class SandboxOut(BaseModel):
    realm_id: UUID
