"""Случайные величины генератора. Источник случайности — только переданный `random.Random`."""

import math
from collections.abc import Mapping, Sequence
from random import Random

from world.config import LogNormal


def chance(rng: Random, probability: float) -> bool:
    return rng.random() < probability


def between(rng: Random, bounds: tuple[int, int]) -> int:
    return rng.randint(bounds[0], bounds[1])


def uniform(rng: Random, bounds: tuple[float, float]) -> float:
    return rng.uniform(bounds[0], bounds[1])


def lognormal(rng: Random, distribution: LogNormal) -> float:
    return rng.lognormvariate(math.log(distribution.median), distribution.sigma)


def noise(rng: Random, sigma: float) -> float:
    """Множитель с медианой 1: помесячный разброс сумм."""
    return rng.lognormvariate(0.0, sigma)


def weighted[T](rng: Random, options: Mapping[T, float]) -> T:
    return rng.choices(list(options), weights=list(options.values()))[0]


def pick[T](rng: Random, options: Sequence[T]) -> T:
    return options[rng.randrange(len(options))]


def scaled(count: int, scale: float) -> int:
    """Число сущностей в масштабе мира; ненулевое число не исчезает при малом масштабе."""
    if count == 0:
        return 0
    return max(1, round(count * scale))
