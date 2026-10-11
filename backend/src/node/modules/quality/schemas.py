"""Схемы входа и выхода API модуля."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class QualityReportOut(BaseModel):
    report_id: UUID
    created_at: datetime
    report: dict[str, Any]
