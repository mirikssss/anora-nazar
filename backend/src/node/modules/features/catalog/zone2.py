"""Признаки зоны 2 «связи»: группы идентичности и координации по индексу связей (Блок 3, зона 2; ревью E)."""

from node.modules.features.passport import FeaturePassport


def _graph(name: str, reason: str | None) -> FeaturePassport:
    return FeaturePassport(
        name=name,
        group="zone2",
        points=("T1", "T4"),
        source="index",
        event_time="occurred_at появления атрибута",
        window="окно индекса связей из политики",
        history="появления за окно индекса",
        missing="not_applicable",
        reason_code=reason,
    )


ZONE2 = (
    _graph("independent_rare_links", "GRAPH_RARE_SHARED_LINKS"),
    _graph("rare_links_weight", "GRAPH_RARE_SHARED_LINKS"),
    _graph("group_applications", "GRAPH_RARE_SHARED_LINKS"),
    _graph("group_subjects", "GRAPH_RARE_SHARED_LINKS"),
    _graph("group_recent_applications", "GRAPH_GROUP_BURST"),
    _graph("group_background_per_window", None),
    _graph("group_burst", "GRAPH_GROUP_BURST"),
    _graph("group_shared_roles", "GRAPH_GROUP_SHARED_ROLE"),
    _graph("group_first_credit_share", "GRAPH_RARE_SHARED_LINKS"),
    _graph("coordination_max_ratio", "GRAPH_COORDINATION_CLUSTER"),
    _graph("coordination_flagged_roles", "GRAPH_COORDINATION_CLUSTER"),
    _graph("coordination_first_credit_share", "GRAPH_COORDINATION_CLUSTER"),
    _graph("employee_linked_share", "F3_EMPLOYEE_CONCENTRATION"),
)
