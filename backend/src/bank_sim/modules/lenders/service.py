"""Кредиторы Б и В в сети: прогон истории мира в общий мир оператора (право history, received_at мира) и заявки
людей сценариев в контуре песочницы в реальном времени. Тот же клиент OPRF, что у узла."""

from collections import Counter
from collections.abc import Callable, Sequence
from datetime import timedelta
from itertools import groupby
from uuid import UUID

from bank_sim.modules.lenders import domain
from bank_sim.modules.lenders.domain import LenderApplication, Refs
from bank_sim.network_gateway import NetworkGateway
from bank_sim.settings import LendersConfig
from shared.network.client import NetworkClient
from world import World

Progress = Callable[[str, int, int], None]


def _tokenize(client: NetworkClient, realm_id: UUID | None, apps: Sequence[LenderApplication]) -> Refs:
    return client.tokenize(realm_id, list(dict.fromkeys(item for app in apps for item in domain.identifiers(app))))


def _send(
    client: NetworkClient, realm_id: UUID | None, apps: Sequence[LenderApplication], refs: Refs, delay: timedelta | None
) -> Counter[str]:
    out = client.send_activity(realm_id, [event for app in apps for event in domain.events(app, refs, delay)])
    results = [r for app in apps if (r := domain.confirmed_result(app, refs)) is not None]
    if results:
        client.send_confirmed(realm_id, results)
    return Counter(accepted=out.accepted, duplicates=out.duplicates, conflicts=len(out.conflicts), results=len(results))


def replay_history(
    network: NetworkGateway, world: World, config: LendersConfig, progress: Progress
) -> dict[str, Counter[str]]:
    """Заявки, выдачи, переводы и результаты дел кредиторов мира — в общий мир оператора. Повтор безопасен: тот же
    event_id с тем же содержимым — дубль."""
    delay = timedelta(seconds=config.delivery_delay_seconds)
    summary: dict[str, Counter[str]] = {}
    apps = sorted((domain.from_world(r) for r in world.other_lenders), key=lambda a: a.lender)
    for code, group in groupby(apps, key=lambda a: a.lender):
        records = list(group)
        client = network.history_lender(code, config.timeout_seconds)
        totals: Counter[str] = Counter()
        try:
            for start in range(0, len(records), config.history_chunk):
                chunk = records[start : start + config.history_chunk]
                totals += _send(client, None, chunk, _tokenize(client, None, chunk), delay)
                progress(code, min(start + config.history_chunk, len(records)), len(records))
        finally:
            client.close()
        summary[code] = totals
    return summary


def tokenize(network: NetworkGateway, realm_id: UUID, apps: Sequence[LenderApplication]) -> dict[str, Refs]:
    """Токены заявок сценария — каждым кредитором своим ключом; оператор недоступен — ошибка до первого шага."""
    by_lender: dict[str, Refs] = {}
    for code in sorted({a.lender for a in apps}):
        by_lender[code] = _tokenize(network.lender(code), realm_id, [a for a in apps if a.lender == code])
    return by_lender


def submit(network: NetworkGateway, realm_id: UUID, apps: Sequence[LenderApplication], refs: dict[str, Refs]) -> None:
    """События заявок сценария в контуре песочницы; время получения ставит оператор — так подписки узла их видят."""
    for code in sorted({a.lender for a in apps}):
        _send(network.lender(code), realm_id, [a for a in apps if a.lender == code], refs[code], None)
