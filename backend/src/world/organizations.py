"""Организации мира: районы и махалли, филиалы, сотрудники, помощники хокимов, работодатели, поставщики, товары."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import accumulate
from random import Random

from world.config import CatalogItemParams, Region, RegistrationAge, WorldParams
from world.identifiers import Identifiers
from world.period import Calendar
from world.records import BranchRecord, EmployeeRecord, HelperRecord, SupplierRecord
from world.sampling import between, chance, lognormal, pick, scaled

YEAR = timedelta(days=365)


@dataclass(frozen=True)
class District:
    code: int  # сквозной номер района — он же код района в ПИНФЛ
    name: str
    region: str
    mahallas: tuple[str, ...]


@dataclass(frozen=True)
class Company:
    """Юрлицо для реестра: дата регистрации и численность; growth — численность сейчас / год назад."""

    inn: str
    registered_on: date
    headcount: int
    growth: float

    def headcount_year_ago(self, as_of: date) -> int | None:
        if self.registered_on > as_of - YEAR:
            return None
        return round(self.headcount / self.growth)


@dataclass(frozen=True)
class CatalogItem:
    code: str
    category: str
    unit: str
    market_price: float
    price_sigma: float
    quantity: tuple[int, int]

    @classmethod
    def of(cls, item: CatalogItemParams) -> "CatalogItem":
        return cls(item.code, item.category, item.unit, item.median, item.sigma, item.quantity)


def registration_date(rng: Random, ages: RegistrationAge, reference: date, *, new: bool) -> date:
    return reference - timedelta(days=between(rng, ages.new if new else ages.established))


class SupplierRegistry:
    """Поставщики программ. Поставщик схемы F3 в общий выбор не попадает — им пользуется только схема."""

    def __init__(self, params: WorldParams, ids: Identifiers, rng: Random) -> None:
        self._params = params
        self._ids = ids
        self._rng = rng
        self.records: list[SupplierRecord] = []
        self._companies: dict[str, Company] = {}
        self._pool: dict[tuple[str, str], list[SupplierRecord]] = defaultdict(list)
        self._pool_by_category: dict[str, list[SupplierRecord]] = defaultdict(list)

    def add(self, category: str, district: str, registered_on: date, *, pooled: bool) -> SupplierRecord:
        record = SupplierRecord(
            inn=self._ids.legal_inn(),
            name=self._params.naming.supplier.format(number=len(self.records) + 1),
            category=category,
            district=district,
            registered_on=registered_on,
            account=self._ids.account(),
            headcount=between(self._rng, self._params.organizations.suppliers.headcount),
        )
        growth = lognormal(self._rng, self._params.organizations.employers.headcount_growth)
        self.records.append(record)
        self._companies[record.inn] = Company(record.inn, registered_on, record.headcount, growth)
        if pooled:
            self._pool[(district, category)].append(record)
            self._pool_by_category[category].append(record)
        return record

    def pick(self, rng: Random, district: str, category: str) -> SupplierRecord:
        """Поставщик категории в районе; если в районе нет — любой поставщик категории."""
        local = self._pool.get((district, category))
        return pick(rng, local) if local else pick(rng, self._pool_by_category[category])

    def company(self, inn: str) -> Company:
        return self._companies[inn]


@dataclass
class Organizations:
    districts: tuple[District, ...]
    branches: tuple[BranchRecord, ...]
    employees: tuple[EmployeeRecord, ...]
    helpers: tuple[HelperRecord, ...]
    employers: tuple[Company, ...]
    employer_weights: tuple[float, ...]  # накопленные веса по численности — для выбора места работы
    items: tuple[CatalogItem, ...]
    suppliers: SupplierRegistry
    branches_by_district: dict[str, tuple[str, ...]]
    employees_by_branch: dict[str, tuple[EmployeeRecord, ...]]
    helpers_by_district: dict[str, tuple[HelperRecord, ...]]
    helper_by_mahalla: dict[tuple[str, str], HelperRecord]
    employer_by_inn: dict[str, Company]

    def employee_for(self, rng: Random, district: str) -> EmployeeRecord:
        branch_id = pick(rng, self.branches_by_district[district])
        return pick(rng, self.employees_by_branch[branch_id])

    def helper_of(self, district: str, mahalla: str) -> HelperRecord:
        return self.helper_by_mahalla[(district, mahalla)]

    def company(self, inn: str) -> Company:
        employer = self.employer_by_inn.get(inn)
        return employer if employer is not None else self.suppliers.company(inn)


def _districts(params: WorldParams) -> list[District]:
    naming = params.naming
    mahallas = tuple(naming.mahalla.format(number=n + 1) for n in range(params.organizations.helpers_per_district))
    districts: list[District] = []
    for region in params.organizations.regions:
        for n in range(region.districts):
            name = naming.district.format(region=region.name, number=n + 1)
            districts.append(District(len(districts) + 1, name, region.name, mahallas))
    return districts


def _region_branches(
    params: WorldParams, region: Region, districts: list[District]
) -> tuple[list[BranchRecord], list[EmployeeRecord], dict[str, tuple[str, ...]]]:
    """Филиал b стоит в районе b mod D; район без своего филиала обслуживает филиал d mod B."""
    orgs, naming = params.organizations, params.naming
    branches: list[BranchRecord] = []
    employees: list[EmployeeRecord] = []
    for b in range(orgs.branches_per_region):
        branch_id = f"BR-{region.code}-{b + 1}"
        name = naming.branch.format(region=region.name, number=b + 1)
        branches.append(BranchRecord(branch_id, name, region.name, districts[b % len(districts)].name))
        for e in range(orgs.employees_per_branch):
            display = naming.employee.format(number=e + 1, branch=name)
            employees.append(
                EmployeeRecord(f"EMP-{region.code}-{b + 1}-{e + 1}", branch_id, display, naming.employee_role)
            )
    served: dict[str, tuple[str, ...]] = {}
    for d, district in enumerate(districts):
        own = tuple(branch.id for branch in branches if branch.district == district.name)
        served[district.name] = own or (branches[d % len(branches)].id,)
    return branches, employees, served


def _employers(params: WorldParams, calendar: Calendar, ids: Identifiers, rng: Random) -> list[Company]:
    spec = params.organizations.employers
    employers: list[Company] = []
    for rank in range(1, scaled(spec.count, params.scale) + 1):
        new = chance(rng, spec.new_share)
        employers.append(
            Company(
                inn=ids.legal_inn(),
                registered_on=registration_date(
                    rng, params.organizations.registration_age_days, calendar.start, new=new
                ),
                headcount=max(1, round(spec.max_headcount / rank**spec.size_zipf)),
                growth=lognormal(rng, spec.headcount_growth),
            )
        )
    return employers


def _suppliers(
    params: WorldParams, calendar: Calendar, ids: Identifiers, rng: Random, districts: list[District]
) -> SupplierRegistry:
    """Категории и районы раздаются по кругу, чтобы у каждой пары район × категория был поставщик."""
    registry = SupplierRegistry(params, ids, rng)
    categories = list(dict.fromkeys(item.category for item in params.organizations.items))
    spec = params.organizations.suppliers
    for n in range(max(len(categories), scaled(spec.count, params.scale))):
        district = districts[(n // len(categories)) % len(districts)]
        registered = registration_date(
            rng, params.organizations.registration_age_days, calendar.start, new=chance(rng, spec.new_share)
        )
        registry.add(categories[n % len(categories)], district.name, registered, pooled=True)
    return registry


def build_organizations(params: WorldParams, calendar: Calendar, ids: Identifiers, rng: Random) -> Organizations:
    districts = _districts(params)
    branches: list[BranchRecord] = []
    employees: list[EmployeeRecord] = []
    served: dict[str, tuple[str, ...]] = {}
    for region in params.organizations.regions:
        region_districts = [d for d in districts if d.region == region.name]
        region_branches, region_employees, region_served = _region_branches(params, region, region_districts)
        branches += region_branches
        employees += region_employees
        served |= region_served
    helpers = [
        HelperRecord(f"HLP-{district.code:03d}-{m + 1:02d}", district.name, mahalla)
        for district in districts
        for m, mahalla in enumerate(district.mahallas)
    ]
    employers = _employers(params, calendar, ids, rng)
    by_branch: dict[str, list[EmployeeRecord]] = defaultdict(list)
    for employee in employees:
        by_branch[employee.branch_id].append(employee)
    by_district: dict[str, list[HelperRecord]] = defaultdict(list)
    for helper in helpers:
        by_district[helper.district].append(helper)
    return Organizations(
        districts=tuple(districts),
        branches=tuple(branches),
        employees=tuple(employees),
        helpers=tuple(helpers),
        employers=tuple(employers),
        employer_weights=tuple(accumulate(employer.headcount for employer in employers)),
        items=tuple(CatalogItem.of(item) for item in params.organizations.items),
        suppliers=_suppliers(params, calendar, ids, rng, districts),
        branches_by_district=served,
        employees_by_branch={branch: tuple(staff) for branch, staff in by_branch.items()},
        helpers_by_district={district: tuple(group) for district, group in by_district.items()},
        helper_by_mahalla={(helper.district, helper.mahalla): helper for helper in helpers},
        employer_by_inn={employer.inn: employer for employer in employers},
    )
