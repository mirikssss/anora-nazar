"""Признаки зоны 1 «воля заёмщика» (Блок 3, «Каталог признаков — зона 1»): только онлайн-канал, точка Т1."""

from node.modules.features.passport import FeaturePassport, Missing


def _t1(name: str, source: str, event_time: str, window: str, missing: Missing, reason: str) -> FeaturePassport:
    return FeaturePassport(
        name=name,
        group="zone1",
        points=("T1",),
        source=source,
        event_time=event_time,
        window=window,
        history="сводка источника на момент заявки",
        missing=missing,
        reason_code=reason,
    )


ZONE1 = (
    _t1(
        "minutes_since_access_recovery",
        "session",
        "восстановление доступа",
        "сессия заявки",
        "not_applicable",
        "F1_ACCESS_RECOVERY_BEFORE_APPLICATION",
    ),
    _t1(
        "device_age_days",
        "session",
        "первое использование устройства",
        "вся история",
        "source_unavailable",
        "F1_NEW_DEVICE",
    ),
    _t1(
        "device_subjects_30d",
        "index",
        "появление устройства в заявках",
        "30 дней",
        "not_applicable",
        "F1_DEVICE_SHARED_BY_CLIENTS",
    ),
    _t1(
        "remote_control_or_call",
        "session",
        "флаг сессии",
        "сессия заявки",
        "source_unavailable",
        "F1_REMOTE_CONTROL_OR_CALL",
    ),
    _t1("form_seconds", "session", "заполнение формы", "сессия заявки", "unknown", "F1_FILL_SPEED"),
    _t1("pasted_into_form", "session", "вставка текста", "сессия заявки", "unknown", "F1_FILL_SPEED"),
    _t1("amount_to_spending", "cards", "траты по картам", "6 месяцев", "not_applicable", "F1_AMOUNT_VS_SPENDING"),
    _t1("first_credit", "bureau", "кредитная история", "вся история", "source_unavailable", "F1_FIRST_CREDIT"),
    _t1(
        "days_since_self_ban_lifted",
        "bureau",
        "снятие самозапрета",
        "вся история",
        "not_applicable",
        "F1_SELF_BAN_RECENTLY_LIFTED",
    ),
    _t1("night_application", "application", "время заявки", "момент заявки", "not_applicable", "F1_NIGHT_APPLICATION"),
)
