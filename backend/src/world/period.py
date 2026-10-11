"""Календарь мира: месяцы периода, местное время заявок и перевод в UTC."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from itertools import accumulate
from random import Random
from zoneinfo import ZoneInfo

from world.config import WorldParams

MONTHS_PER_YEAR = 12
SECONDS_PER_HOUR = 3600


def _shift_month(start: date, months: int) -> date:
    index = start.month - 1 + months
    return date(start.year + index // MONTHS_PER_YEAR, index % MONTHS_PER_YEAR + 1, 1)


@dataclass(frozen=True)
class _HourTable:
    hours: tuple[int, ...]
    cumulative: tuple[float, ...]

    @classmethod
    def of(cls, weights: list[float], hours: list[int]) -> "_HourTable":
        return cls(tuple(hours), tuple(accumulate(weights[hour] for hour in hours)))

    def draw(self, rng: Random) -> int:
        return rng.choices(self.hours, cum_weights=self.cumulative)[0]


@dataclass(frozen=True)
class Calendar:
    zone: ZoneInfo
    start: date
    months: int
    night: _HourTable
    day: _HourTable

    @classmethod
    def from_params(cls, params: WorldParams) -> "Calendar":
        weights = params.applications.hour_weights
        night_hours = sorted(set(params.applications.night_hours))
        day_hours = [hour for hour in range(len(weights)) if hour not in night_hours and weights[hour] > 0]
        return cls(
            zone=params.zone,
            start=params.period.start,
            months=params.period.months,
            night=_HourTable.of(weights, night_hours),
            day=_HourTable.of(weights, day_hours),
        )

    @property
    def end_date(self) -> date:
        return _shift_month(self.start, self.months)

    @property
    def start_at(self) -> datetime:
        return self.at(self.start)

    @property
    def end_at(self) -> datetime:
        """Граница истории: факты, полученные позже, в мир не попадают."""
        return self.at(self.end_date)

    @property
    def days(self) -> int:
        return (self.end_date - self.start).days

    def at(self, day: date, moment: time = time()) -> datetime:
        """Местные дата и время → UTC."""
        return datetime.combine(day, moment, tzinfo=self.zone).astimezone(UTC)

    def local(self, moment: datetime) -> datetime:
        return moment.astimezone(self.zone)

    def month_window(self, index: int) -> tuple[date, int]:
        first = _shift_month(self.start, index)
        return first, (_shift_month(self.start, index + 1) - first).days

    def month_index(self, moment: datetime) -> int:
        day = self.local(moment).date()
        return (day.year - self.start.year) * MONTHS_PER_YEAR + day.month - self.start.month

    def months_before(self, moment: datetime, count: int) -> list[str]:
        """Полные месяцы перед месяцем момента, от старого к новому, в формате ГГГГ-ММ."""
        current = self.local(moment).date().replace(day=1)
        return [_shift_month(current, -offset).strftime("%Y-%m") for offset in range(count, 0, -1)]

    def window_start(self, rng: Random, days: int) -> date:
        """Случайное начало окна в `days` дней, целиком лежащего в периоде."""
        latest = max(self.days - days, 0)
        return self.start + timedelta(days=rng.randint(0, latest))

    def contains(self, moment: datetime) -> bool:
        return self.start_at <= moment < self.end_at

    def around(self, rng: Random, moment: datetime, nearest: timedelta, farthest: timedelta) -> datetime | None:
        """Момент на случайном расстоянии от `moment` в пределах [nearest, farthest], раньше или позже;
        если сторона выходит за период — другая сторона, если обе — None."""
        offset = timedelta(seconds=rng.uniform(nearest.total_seconds(), farthest.total_seconds()))
        sides = [moment + offset, moment - offset]
        rng.shuffle(sides)
        return next((candidate for candidate in sides if self.contains(candidate)), None)

    def moment(self, rng: Random, first_day: date, days: int, *, night: bool) -> datetime:
        """Случайный момент в окне: день равномерно, час — по весам ночных или дневных часов."""
        span = max(min(days, (self.end_date - first_day).days), 1)
        day = first_day + timedelta(days=rng.randrange(span))
        hour = (self.night if night else self.day).draw(rng)
        offset = timedelta(hours=hour, seconds=rng.randrange(SECONDS_PER_HOUR))
        return (datetime.combine(day, time(), tzinfo=self.zone) + offset).astimezone(UTC)
