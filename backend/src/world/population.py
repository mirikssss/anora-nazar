"""Люди и домохозяйства: ПИНФЛ, телефоны, устройства, адреса, работа, карта в банке, доход, ИНПС.

Ловушки населения: семья с одним телефоном или общим планшетом, общежитие — шумный хаб по адресу.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from random import Random

from world.config import Naming, WorldParams
from world.identifiers import Identifiers
from world.organizations import District, Organizations
from world.period import Calendar
from world.sampling import between, chance, lognormal, pick, scaled, uniform, weighted


@dataclass(frozen=True)
class Person:
    pinfl: str
    phone: str
    device_id: str
    device_first_seen: datetime
    household: int
    district: str
    mahalla: str
    address: str
    in_dormitory: bool
    employer_inn: str | None
    card_in_bank: bool
    inps_available: bool
    monthly_income: int
    monthly_spending: int
    account: str


class AddressBook:
    """Адреса по шаблону; номер дома растёт внутри махалли, поэтому адрес домохозяйства уникален."""

    def __init__(self, naming: Naming) -> None:
        self._naming = naming
        self._houses: dict[tuple[str, str], int] = defaultdict(int)
        self._dormitories: dict[str, int] = defaultdict(int)

    def household(self, district: str, mahalla: str) -> str:
        self._houses[(district, mahalla)] += 1
        return self._naming.address.format(district=district, mahalla=mahalla, house=self._houses[(district, mahalla)])

    def dormitory(self, district: str) -> str:
        self._dormitories[district] += 1
        return self._naming.dormitory.format(district=district, number=self._dormitories[district])


@dataclass(frozen=True)
class _Home:
    household: int
    district: District
    mahalla: str
    address: str
    in_dormitory: bool
    phone: str | None
    device: tuple[str, datetime] | None


@dataclass(frozen=True)
class Population:
    people: tuple[Person, ...]
    addresses: AddressBook
    by_district: dict[str, tuple[int, ...]]
    by_mahalla: dict[tuple[str, str], tuple[int, ...]]
    by_employer: dict[str, tuple[int, ...]]
    card_holders: tuple[int, ...]

    def random(self, rng: Random) -> Person:
        return pick(rng, self.people)

    def sample(
        self,
        rng: Random,
        pools: Sequence[Sequence[int]],
        size: int,
        *,
        distinct_households: bool = False,
        exclude_dormitories: bool = False,
    ) -> list[Person]:
        """Разные люди из пулов по порядку: следующий пул берётся, только если в предыдущем не хватило."""
        chosen: dict[int, Person] = {}
        households: dict[int, None] = {}
        for pool in pools:
            for index in rng.sample(pool, len(pool)):
                person = self.people[index]
                if index in chosen or (exclude_dormitories and person.in_dormitory):
                    continue
                if distinct_households and person.household in households:
                    continue
                chosen[index] = person
                households[person.household] = None
                if len(chosen) == size:
                    return list(chosen.values())
        return list(chosen.values())


class _PopulationBuilder:
    def __init__(
        self, params: WorldParams, calendar: Calendar, orgs: Organizations, ids: Identifiers, rng: Random
    ) -> None:
        self._params = params
        self._spec = params.population
        self._calendar = calendar
        self._orgs = orgs
        self._ids = ids
        self._rng = rng
        self.addresses = AddressBook(params.naming)
        self.people: list[Person] = []
        self._households = 0

    def build(self) -> Population:
        total = scaled(self._spec.people, self._params.scale)
        for _ in range(scaled(self._spec.dormitories.count, self._params.scale)):
            district = pick(self._rng, self._orgs.districts)
            mahalla = pick(self._rng, district.mahallas)
            address = self.addresses.dormitory(district.name)
            # каждый жилец общежития — отдельное домохозяйство с общим адресом
            for _ in range(min(between(self._rng, self._spec.dormitories.residents), total - len(self.people))):
                self._add(self._home(district, mahalla, address, in_dormitory=True))
        while len(self.people) < total:
            size = min(weighted(self._rng, self._spec.household_sizes), total - len(self.people))
            district = pick(self._rng, self._orgs.districts)
            mahalla = pick(self._rng, district.mahallas)
            home = self._home(district, mahalla, self.addresses.household(district.name, mahalla), in_dormitory=False)
            for _ in range(size):
                self._add(home)
        return self._index()

    def _device(self) -> tuple[str, datetime]:
        age = timedelta(days=uniform(self._rng, self._spec.device_age_days))
        return self._ids.device(), self._calendar.start_at - age

    def _home(self, district: District, mahalla: str, address: str, *, in_dormitory: bool) -> _Home:
        self._households += 1
        shared_phone = not in_dormitory and chance(self._rng, self._spec.shared_phone_household_share)
        shared_device = not in_dormitory and chance(self._rng, self._spec.shared_device_household_share)
        return _Home(
            household=self._households,
            district=district,
            mahalla=mahalla,
            address=address,
            in_dormitory=in_dormitory,
            phone=self._ids.phone() if shared_phone else None,
            device=self._device() if shared_device else None,
        )

    def _birth_date(self) -> date:
        year = between(self._rng, self._spec.birth_years)
        first = date(year, 1, 1)
        return first + timedelta(days=self._rng.randrange((date(year + 1, 1, 1) - first).days))

    def _add(self, home: _Home) -> None:
        rng, spec = self._rng, self._spec
        device_id, first_seen = home.device or self._device()
        inps = chance(rng, spec.inps_available_share)
        employer = rng.choices(self._orgs.employers, cum_weights=self._orgs.employer_weights)[0] if inps else None
        income = round(lognormal(rng, spec.monthly_income))
        self.people.append(
            Person(
                pinfl=self._ids.pinfl(self._birth_date(), chance(rng, spec.male_share), home.district.code),
                phone=home.phone or self._ids.phone(),
                device_id=device_id,
                device_first_seen=first_seen,
                household=home.household,
                district=home.district.name,
                mahalla=home.mahalla,
                address=home.address,
                in_dormitory=home.in_dormitory,
                employer_inn=employer.inn if employer else None,
                card_in_bank=chance(rng, spec.card_in_bank_share),
                inps_available=inps,
                monthly_income=income,
                monthly_spending=round(income * lognormal(rng, spec.spending_to_income)),
                account=self._ids.account(),
            )
        )

    def _index(self) -> Population:
        by_district: dict[str, list[int]] = defaultdict(list)
        by_mahalla: dict[tuple[str, str], list[int]] = defaultdict(list)
        by_employer: dict[str, list[int]] = defaultdict(list)
        for index, person in enumerate(self.people):
            by_district[person.district].append(index)
            by_mahalla[(person.district, person.mahalla)].append(index)
            if person.employer_inn is not None:
                by_employer[person.employer_inn].append(index)
        return Population(
            people=tuple(self.people),
            addresses=self.addresses,
            by_district={key: tuple(value) for key, value in by_district.items()},
            by_mahalla={key: tuple(value) for key, value in by_mahalla.items()},
            by_employer={key: tuple(value) for key, value in by_employer.items()},
            card_holders=tuple(i for i, person in enumerate(self.people) if person.card_in_bank),
        )


def build_population(
    params: WorldParams, calendar: Calendar, orgs: Organizations, ids: Identifiers, rng: Random
) -> Population:
    return _PopulationBuilder(params, calendar, orgs, ids, rng).build()
