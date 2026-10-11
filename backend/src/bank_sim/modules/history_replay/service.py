"""Прогон мира: персонал — в базу имитатора, история — в узел пакетами по времени получения."""

from collections import Counter
from collections.abc import Callable

from sqlalchemy.orm import Session

from bank_sim.modules.staff import service as staff
from shared.http import ServiceClient
from world import World


def store_staff(session: Session, world: World) -> None:
    staff.upsert_world(
        session,
        [{"id": b.id, "name": b.name, "district": b.district} for b in world.branches],
        [
            {"id": e.id, "branch_id": e.branch_id, "display_name": e.display_name, "role": e.role}
            for e in world.employees
        ],
    )


def replay(client: ServiceClient, world: World, batch_size: int, progress: Callable[[int, int], None]) -> Counter[str]:
    """Пакеты идут строго по порядку истории; повтор безопасен — узел узнаёт оценки и события по ключам."""
    outcomes: Counter[str] = Counter()
    total = len(world.history)
    for start in range(0, total, batch_size):
        batch = world.history[start : start + batch_size]
        body = {"items": [item.model_dump(mode="json") for item in batch]}
        result = client.call("POST", "/v1/history/batches", json=body)
        outcomes.update(result["outcomes"])
        progress(min(start + batch_size, total), total)
    return outcomes
