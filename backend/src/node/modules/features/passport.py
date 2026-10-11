"""Паспорт признака: точки, время события и получения, окно, нужная история, поведение при отсутствии, версия."""

from dataclasses import dataclass
from typing import Literal

Missing = Literal["not_applicable", "unknown", "source_unavailable"]


@dataclass(frozen=True)
class FeaturePassport:
    name: str
    points: tuple[str, ...]
    source: str
    event_time: str
    received_time: str
    window: str
    history: str
    missing: Missing
    version: int
