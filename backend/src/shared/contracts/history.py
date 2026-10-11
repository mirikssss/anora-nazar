"""История синтетического мира: что прогон отдаёт узлу через его интерфейсы — оценки Т1/Т4 и события.

received_at — когда банк узнал факт в истории мира; прогон идёт строго по нему.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from shared.contracts.application import ApplicationSnapshot
from shared.events import EventEnvelope


class _Item(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class HistoryAssessment(_Item):
    kind: Literal["assessment"] = "assessment"
    point: Literal["T1", "T4"]
    application_id: str = Field(min_length=1, max_length=32)
    application_version: int = Field(ge=1)
    snapshot: ApplicationSnapshot
    occurred_at: datetime
    received_at: datetime


class HistoryEvent(_Item):
    kind: Literal["event"] = "event"
    envelope: EventEnvelope
    received_at: datetime


HistoryItem = Annotated[HistoryAssessment | HistoryEvent, Field(discriminator="kind")]
