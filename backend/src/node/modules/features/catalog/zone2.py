"""Признаки зоны 2 «связи»: граф по индексу связей (Блок 3, «Каталог признаков — зона 2»)."""

from node.modules.features.passport import FeaturePassport


def _from_index(name: str) -> FeaturePassport:
    return FeaturePassport(
        name=name,
        points=("T1", "T4"),
        source="index",
        event_time="occurred_at появления атрибута",
        received_time="received_at появления атрибута",
        window="окно индекса связей из политики",
        history="появления за окно индекса",
        missing="not_applicable",
        version=1,
    )


ZONE2 = tuple(
    _from_index(name)
    for name in (
        "independent_rare_links",
        "rare_links_weight",
        "group_applications",
        "group_subjects",
        "group_recent_applications",
        "group_background_per_window",
        "group_burst",
        "group_shared_roles",
    )
)
