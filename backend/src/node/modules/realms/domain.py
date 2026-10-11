"""Чистая логика модуля без ввода-вывода."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RealmContext:
    """Контур запроса: куда пишем и что видим."""

    id: UUID
    is_sandbox: bool
    world_id: UUID

    @property
    def visible_ids(self) -> tuple[UUID, ...]:
        """Песочница видит общий мир и себя; общий мир видит только себя."""
        return (self.world_id, self.id) if self.is_sandbox else (self.id,)
