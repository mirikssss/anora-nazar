"""Прогон мира: персонал и справочники программ — в базу имитатора, история — в узел пакетами по времени получения."""

from collections import Counter
from collections.abc import Callable

from sqlalchemy.orm import Session

from bank_sim.modules.program_platform import service as program
from bank_sim.modules.staff import service as staff
from shared.http import ServiceClient
from world import World


def store_staff(session: Session, world: World) -> None:
    """Персонал и справочники программ мира — те же, что в истории узла."""
    program.upsert_world(
        session,
        [{"id": h.id, "district": h.district, "mahalla": h.mahalla} for h in world.helpers],
        [
            {
                "inn": s.inn,
                "name": s.name,
                "category": s.category,
                "district": s.district,
                "registered_on": s.registered_on,
                "account": s.account,
            }
            for s in world.suppliers
        ],
    )
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
