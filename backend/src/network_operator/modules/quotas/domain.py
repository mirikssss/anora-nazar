"""Чистая логика модуля: квота OPRF по числу реальных заявок кредитора."""

from dataclasses import dataclass

from network_operator.settings import QuotasConfig


@dataclass(frozen=True)
class Allowance:
    """Вычислений OPRF за скользящее окно: использовано и предел = запас + коэффициент × заявок за окно."""

    used: int
    limit: int
    window_seconds: int

    def admits(self, requested: int) -> bool:
        return self.used + requested <= self.limit


def allowance(used: int, applications: int, limits: QuotasConfig) -> Allowance:
    return Allowance(
        used=used,
        limit=limits.reserve + limits.per_application * applications,
        window_seconds=limits.window_seconds,
    )
