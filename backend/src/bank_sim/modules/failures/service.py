"""Кнопки сбоев песочницы: потерять итог, узел недоступен, очередь отстаёт, сеть недоступна, повтор с другой
суммой."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from bank_sim.modules.failures import repository
from bank_sim.modules.failures.models import FailureFlags
from bank_sim.modules.failures.schemas import Flags, FlagsPatch
from bank_sim.network_gateway import NetworkGateway
from shared.errors import ConflictError, UpstreamUnavailableError


def flags(session: Session, realm_id: UUID) -> Flags:
    row = repository.get(session, realm_id)
    if row is None:
        return Flags(lose_outcome=False, node_unavailable=False, queue_lag=False, network_unavailable=False)
    return Flags(
        lose_outcome=row.lose_outcome,
        node_unavailable=row.node_unavailable,
        queue_lag=row.queue_lag,
        network_unavailable=row.network_unavailable,
    )


def update(session: Session, realm_id: UUID, patch: FlagsPatch, now: datetime) -> Flags:
    current = flags(session, realm_id).model_copy(update=patch.model_dump(exclude_none=True))
    row = repository.get(session, realm_id)
    if row is None:
        repository.add(session, FailureFlags(realm_id=realm_id, updated_at=now, **current.model_dump()))
    else:
        row.lose_outcome, row.node_unavailable, row.queue_lag, row.network_unavailable = (
            current.lose_outcome,
            current.node_unavailable,
            current.queue_lag,
            current.network_unavailable,
        )
        row.updated_at = now
    return current


def switch_network(network: NetworkGateway | None, realm_id: UUID, unavailable: bool) -> None:
    """Сбой «сеть недоступна» включает оператор сети для контура песочницы: на запросы узла и кредиторов Б и В
    он отвечает 503, узел решает без сети с причиной «сеть недоступна»."""
    if network is None:
        raise ConflictError("network_not_configured", "Сеть кредиторов на стенде не настроена")
    network.set_outage(realm_id, unavailable)


def ensure_node_reachable(current: Flags) -> None:
    if current.node_unavailable:
        raise UpstreamUnavailableError("node_unavailable", "Узел недоступен: операция ждёт его восстановления")


def delivery_held(current: Flags) -> bool:
    """Очередь событий песочницы в узел стоит: включён сбой «очередь отстаёт» или «узел недоступен»."""
    return current.queue_lag or current.node_unavailable
