"""Паспорт признака: точки, группа, время события и получения, окно, нужная история, поведение при отсутствии,
код причины для вклада в балл, версия определения.
"""

from dataclasses import dataclass
from typing import Literal

Missing = Literal["not_applicable", "unknown", "source_unavailable"]
Group = Literal["context", "zone1", "zone2", "zone3"]
FeaturePoint = Literal["T1", "T4"]


@dataclass(frozen=True)
class FeaturePassport:
    name: str
    group: Group
    points: tuple[FeaturePoint, ...]
    source: str
    event_time: str
    window: str
    history: str
    missing: Missing
    reason_code: str | None
    version: int = 1
    received_time: str = "received_at факта у узла"
