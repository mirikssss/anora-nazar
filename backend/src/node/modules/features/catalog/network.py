"""Признаки сети кредиторов: счётчики оператора по чужим кредиторам (Блок 3; network_operator/SPEC.md).

Сеть выключена или не ответила — пропуск: модели с признаками сети тогда не запускаются, работают локальные.
"""

from node.modules.features.passport import FeatureFieldPoints, FeaturePassport


def _network(name: str, points: FeatureFieldPoints, window: str, reason: str | None) -> FeaturePassport:
    return FeaturePassport(
        name=name,
        group="network",
        points=points,
        source="network",
        event_time="occurred_at события у другого кредитора",
        received_time="received_at события у оператора сети",
        window=window,
        history="события других кредиторов за окно",
        missing="source_unavailable",
        reason_code=reason,
    )


NETWORK = (
    _network("net_pinfl_lenders_1h", ("T1", "T4"), "1 ч", "NETWORK_PINFL_SERIES"),
    _network("net_pinfl_lenders_7d", ("T1", "T4"), "7 дней", "NETWORK_PINFL_SERIES"),
    _network("net_phone_people_24h", ("T1", "T4"), "24 ч", "NETWORK_SHARED_PHONE"),
    _network("net_phone_people_30d", ("T1", "T4"), "30 дней", "NETWORK_SHARED_PHONE"),
    _network("net_device_people_30d", ("T1",), "30 дней", "NETWORK_SHARED_DEVICE"),
    _network("net_supplier_borrowers_30d", ("T4",), "30 дней", "NETWORK_SUPPLIER_SPREAD"),
    _network("net_supplier_lenders_30d", ("T4",), "30 дней", "NETWORK_SUPPLIER_SPREAD"),
    _network("net_confirmed_match", ("T1", "T4"), "до момента решения", "NETWORK_CONFIRMED_CASE_IDENTIFIER"),
)
