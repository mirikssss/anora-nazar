"""Накопитель истории: проверяет payload моделями контракта, выдаёт детерминированные event_id, сортирует."""

from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel

from shared.contracts.application import ApplicationSnapshot
from shared.contracts.facts import FACTS
from shared.contracts.history import HistoryAssessment, HistoryEvent
from shared.events import EventEnvelope

SCHEMA_VERSION = 1
_EVENT_TYPES: dict[type[BaseModel], str] = {model: event_type for event_type, model in FACTS.items()}


class HistorySink:
    """Элемент получает порядковый номер при добавлении; позже границы истории в мир ничего не попадает."""

    def __init__(self, seed: int, version: str, cutoff: datetime) -> None:
        self._namespace = uuid5(NAMESPACE_URL, f"anora-nazar/world/{version}/{seed}")
        self._cutoff = cutoff
        self._sequence = 0
        self._items: list[tuple[datetime, int, HistoryAssessment | HistoryEvent]] = []

    def _next(self) -> int:
        self._sequence += 1
        return self._sequence

    def assessment(self, application_id: str, version: int, snapshot: ApplicationSnapshot, at: datetime) -> None:
        if at >= self._cutoff:
            return
        item = HistoryAssessment(
            point="T1" if snapshot.channel == "online" else "T4",
            application_id=application_id,
            application_version=version,
            snapshot=snapshot,
            occurred_at=at,
            received_at=at,
        )
        self._items.append((at, self._next(), item))

    def fact(
        self,
        payload: BaseModel,
        *,
        source: str,
        entity_type: str,
        entity_id: str,
        occurred_at: datetime,
        received_at: datetime,
        entity_version: int | None = None,
    ) -> None:
        if received_at >= self._cutoff:
            return
        sequence = self._next()
        envelope = EventEnvelope(
            event_id=uuid5(self._namespace, str(sequence)),
            source=source,
            type=_EVENT_TYPES[type(payload)],
            entity_type=entity_type,
            entity_id=entity_id,
            entity_version=entity_version,
            occurred_at=occurred_at,
            schema_version=SCHEMA_VERSION,
            payload=payload.model_dump(mode="json"),
        )
        self._items.append((received_at, sequence, HistoryEvent(envelope=envelope, received_at=received_at)))

    def items(self) -> list[HistoryAssessment | HistoryEvent]:
        return [item for _, _, item in sorted(self._items, key=lambda entry: (entry[0], entry[1]))]
