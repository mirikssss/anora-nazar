"""Схемы входа и выхода API модуля."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from shared.contracts.network import CONTRACT_VERSION


class QuotaOut(BaseModel):
    used: int = Field(description="Вычислений OPRF за окно квоты")
    limit: int = Field(description="Запас + коэффициент × заявок кредитора за окно")
    window_seconds: int


class NotificationsOut(BaseModel):
    pending: int
    delivered: int
    failed: int


class LenderStatsOut(BaseModel):
    lender: str
    contour: Literal["world", "sandbox"]
    events: int = Field(description="Заявки, выдачи и переводы без исправлений и отмен")
    applications: int
    confirmed_results: int
    queries: int = Field(description="Запросов счётчиков по заявкам")
    oprf_evaluations: int
    quota: QuotaOut
    active_watches: int = Field(description="Заявок с действующей подпиской на совпадения")
    notifications: NotificationsOut


class StatsOut(BaseModel):
    contract: str = CONTRACT_VERSION
    generated_at: datetime
    realm_id: UUID | None
    lenders: list[LenderStatsOut]
