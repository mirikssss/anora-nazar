"""Признаки зоны 3 «суть проекта» (Блок 3, зона 3): цена, концентрации, доход; плюс контекст канала."""

from node.modules.features.passport import FeaturePassport, FeaturePoint, Group, Missing


def _feature(
    name: str,
    points: tuple[FeaturePoint, ...],
    source: str,
    window: str,
    missing: Missing,
    reason: str | None,
    group: Group = "zone3",
) -> FeaturePassport:
    return FeaturePassport(
        name=name,
        group=group,
        points=points,
        source=source,
        event_time="время события источника",
        window=window,
        history="факты источника с received_at ≤ as_of",
        missing=missing,
        reason_code=reason,
    )


T4: tuple[FeaturePoint, ...] = ("T4",)
BOTH: tuple[FeaturePoint, ...] = ("T1", "T4")

ZONE3 = (
    _feature("price_robust_z", T4, "index", "по уровням сравнения", "unknown", "F3_PRICE_ABOVE_COMPARABLES"),
    _feature("price_comparables_level", T4, "index", "по уровням сравнения", "unknown", None),
    _feature("supplier_age_days", T4, "registry", "вся история", "source_unavailable", "F3_SUPPLIER_NEW"),
    _feature("supplier_concentration_ratio", T4, "index", "90 дней", "not_applicable", "F3_SUPPLIER_CONCENTRATION"),
    _feature("branch_supplier_hhi", T4, "index", "90 дней", "not_applicable", "F3_SUPPLIER_CONCENTRATION"),
    _feature("employee_concentration_ratio", T4, "index", "90 дней", "not_applicable", "F3_EMPLOYEE_CONCENTRATION"),
    _feature(
        "helper_burst_ratio", T4, "index", "10 дней против 80", "not_applicable", "F3_HELPER_RECOMMENDATION_BURST"
    ),
    _feature("helper_supplier_share", T4, "index", "90 дней", "not_applicable", "F3_HELPER_RECOMMENDATION_BURST"),
    _feature("income_jump_ratio", BOTH, "inps", "3 месяца против 12", "source_unavailable", "F3_INCOME_JUMP"),
    _feature("income_cusum_alarm", BOTH, "inps", "15 месяцев", "source_unavailable", "F3_INCOME_JUMP"),
    _feature("voluntary_contributions_share", BOTH, "inps", "3 месяца", "unknown", "F3_VOLUNTARY_CONTRIBUTIONS_SHARE"),
    _feature(
        "employer_age_days", BOTH, "registry", "вся история", "source_unavailable", "F3_NEW_EMPLOYER_HIRING_SURGE"
    ),
    _feature(
        "employer_headcount_growth", BOTH, "registry", "год", "source_unavailable", "F3_NEW_EMPLOYER_HIRING_SURGE"
    ),
    _feature("employer_cohort_size", BOTH, "index", "30 дней", "not_applicable", "F3_NEW_EMPLOYER_HIRING_SURGE"),
    _feature("employer_cohort_income_alarm_share", BOTH, "inps", "30 дней", "unknown", "F3_NEW_EMPLOYER_HIRING_SURGE"),
)

CONTEXT = (
    _feature("channel_online", BOTH, "application", "момент заявки", "not_applicable", None, group="context"),
    _feature("loan_amount_log", BOTH, "application", "момент заявки", "not_applicable", None, group="context"),
)
