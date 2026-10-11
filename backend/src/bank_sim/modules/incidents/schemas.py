"""Схемы входа и выхода API модуля."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    typology: str
    result: str
    application_ids: list[str]
    case_key: str
    created_at: datetime
