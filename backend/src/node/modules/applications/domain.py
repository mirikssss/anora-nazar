"""Чистая логика модуля без ввода-вывода: порядок версий."""

from enum import StrEnum


class VersionOutcome(StrEnum):
    APPLIED = "applied"  # следующая версия — применена
    SAME = "same"  # та же версия с тем же снимком — ничего не меняет
    STALE = "stale"  # старая версия — хранится для аудита, состояние не откатывает
    GAP = "gap"  # версия из будущего — ждём пропущенную


def classify_version(current: int | None, incoming: int) -> VersionOutcome:
    """Порядок версий внутри заявки. current=None — заявки ещё нет, ждём версию 1."""
    expected = 1 if current is None else current + 1
    if incoming == expected:
        return VersionOutcome.APPLIED
    if current is not None and incoming == current:
        return VersionOutcome.SAME
    if current is not None and incoming < current:
        return VersionOutcome.STALE
    return VersionOutcome.GAP
