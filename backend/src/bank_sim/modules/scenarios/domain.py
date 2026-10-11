"""Чистая логика сценариев: определения из сида, участники запуска в форматах мира и черновики заявок.

Участники генерируются заново на каждый запуск, детерминированно от песочницы и номера запуска: повторный
запуск не связывается с прошлым через общие ПИНФЛ, телефоны и устройства.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from random import Random
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from bank_sim.modules.sessions.domain import SessionProfile
from bank_sim.modules.sources.domain import BureauProfile, CardsProfile, CompanyProfile, InpsProfile, SourceProfile
from world.identifiers import Identifiers

Level = Literal["green", "yellow", "red"]
BranchChoice = Literal["online", "helper"] | Annotated[int, Field(ge=1)]


class ScenarioError(ValueError):
    """Сценарий нельзя выполнить на этих справочниках (например, мир не загружен)."""


class _Spec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class HomeSpec(_Spec):
    """Где живёт человек: район и махалля n-го помощника хокима мира, или другая махалля того же района."""

    helper: int = Field(ge=1)
    mahalla: Literal["same", "other"] = "same"


class PersonSpec(_Spec):
    birth_years: tuple[int, int]
    male: bool
    home: HomeSpec | None = None
    employer: str | None = None  # компания сценария с ролью employer

    @model_validator(mode="after")
    def _years(self) -> Self:
        if self.birth_years[0] > self.birth_years[1]:
            raise ValueError("Годы рождения: нижняя граница больше верхней")
        return self


class CompanySpec(_Spec):
    role: Literal["employer", "supplier"]
    profile: CompanyProfile


class FactsStep(_Spec):
    """Ответы источников банка о людях — событиями в узел до заявки."""

    kind: Literal["facts"]
    people: list[str] = Field(min_length=1)
    bureau: BureauProfile | None = None
    cards: CardsProfile | None = None
    inps: InpsProfile | None = None

    @model_validator(mode="after")
    def _some(self) -> Self:
        if self.bureau is None and self.cards is None and self.inps is None:
            raise ValueError("Шаг фактов без единого источника")
        return self

    @property
    def profile(self) -> SourceProfile:
        return SourceProfile(bureau=self.bureau, cards=self.cards, inps=self.inps)


class CompanyStep(_Spec):
    """Записи реестра юрлиц о компаниях сценария."""

    kind: Literal["company"]
    companies: list[str] = Field(min_length=1)


class SharedSpec(_Spec):
    """Общие для нескольких заявок идентификаторы: имя — внутри запуска, значение генерируется."""

    phone: str | None = None
    device: str | None = None
    address: str | None = None


class LoanSpec(_Spec):
    amount: int | None = Field(default=None, gt=0)  # у программной заявки сумма — цена × количество
    term_months: int = Field(gt=0, le=600)


class ProgramSpec(_Spec):
    helper: int = Field(ge=1)  # n-й помощник хокима мира (по id)
    supplier: str  # компания сценария с ролью supplier
    item: str  # код товара из каталога мира
    price_factor: float = Field(gt=0)  # цена за единицу = медиана рынка × множитель
    quantity: int = Field(ge=1)


class ApplicationStep(_Spec):
    """Заявки через конвейер: по одной на человека; онлайн-канал приложения или филиал."""

    kind: Literal["application"]
    channel: Literal["online", "program"]
    people: list[str] = Field(min_length=1)
    branch: BranchChoice
    loan: LoanSpec
    shared: SharedSpec = SharedSpec()
    session: SessionProfile | None = None
    program: ProgramSpec | None = None

    @model_validator(mode="after")
    def _channel(self) -> Self:
        if self.channel == "online":
            if self.program is not None or self.loan.amount is None or self.branch == "helper":
                raise ValueError("Онлайн-заявке нужна сумма, без программной части и без филиала помощника")
        elif self.program is None or self.session is not None or self.loan.amount is not None:
            raise ValueError("Программной заявке нужна программная часть, без сессии приложения и без суммы")
        elif self.branch == "online":
            raise ValueError("Программная заявка подаётся в филиале")
        return self


Step = Annotated[FactsStep | CompanyStep | ApplicationStep, Field(discriminator="kind")]


class Expected(_Spec):
    level: Level
    action: str = Field(min_length=1, max_length=64)


class ScenarioSpec(_Spec):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    zone: Literal[1, 2, 3] | None
    title: str = Field(min_length=1, max_length=128)
    summary: str = Field(min_length=1, max_length=1024)
    expected: Expected
    expected_summary: str = Field(min_length=1, max_length=1024)
    people: dict[str, PersonSpec] = Field(min_length=1)
    companies: dict[str, CompanySpec] = Field(default_factory=dict)
    steps: list[Step] = Field(min_length=1)

    @model_validator(mode="after")
    def _references(self) -> Self:
        errors: list[str] = []
        for ref, person in self.people.items():
            if person.employer is not None and self._role(person.employer) != "employer":
                errors.append(f"работодатель {person.employer} у {ref} — не компания-работодатель сценария")
        for step in self.steps:
            people = step.people if isinstance(step, FactsStep | ApplicationStep) else []
            errors += [f"нет человека {ref}" for ref in people if ref not in self.people]
            if isinstance(step, CompanyStep):
                errors += [f"нет компании {ref}" for ref in step.companies if ref not in self.companies]
            program = step.program if isinstance(step, ApplicationStep) else None
            if program is not None and self._role(program.supplier) != "supplier":
                errors.append(f"поставщик {program.supplier} — не компания-поставщик сценария")
        if not any(isinstance(step, ApplicationStep) for step in self.steps):
            errors.append("в сценарии нет заявки")
        if errors:
            raise ValueError(f"Сценарий {self.code}: " + "; ".join(errors))
        return self

    def _role(self, ref: str) -> str | None:
        company = self.companies.get(ref)
        return None if company is None else company.role


class ScenarioBook(_Spec):
    version: str = Field(min_length=1)
    scenarios: list[ScenarioSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> Self:
        codes = [s.code for s in self.scenarios]
        if len(set(codes)) != len(codes):
            raise ValueError("Коды сценариев повторяются")
        return self

    def find(self, code: str) -> ScenarioSpec | None:
        return next((s for s in self.scenarios if s.code == code), None)


@dataclass(frozen=True)
class HelperRef:
    id: str
    district: str
    mahalla: str


@dataclass(frozen=True)
class BranchRef:
    id: str
    district: str
    employee_id: str


@dataclass(frozen=True)
class ItemRef:
    unit: str
    median_price: float


@dataclass(frozen=True)
class WorldRefs:
    """Справочники, на которых строится запуск: мир из базы имитатора, форматы и каталог — из параметров мира."""

    helpers: tuple[HelperRef, ...]  # по возрастанию id
    branches: tuple[BranchRef, ...]  # филиалы с сотрудниками, по возрастанию id
    online_branch: str
    catalog: dict[str, ItemRef]
    address_format: str
    operator_codes: tuple[str, ...]
    pinfl_district_codes: tuple[int, int]
    house_numbers: tuple[int, int]

    def helper(self, n: int) -> HelperRef:
        if not self.helpers:
            raise ScenarioError("Справочники мира не загружены: сначала прогон мира (python -m bank_sim world)")
        if n > len(self.helpers):
            raise ScenarioError(f"В мире {len(self.helpers)} помощников хокима, а сценарию нужен {n}-й")
        return self.helpers[n - 1]

    def branch(self, n: int) -> BranchRef:
        if n > len(self.branches):
            raise ScenarioError(f"Филиалов с сотрудниками {len(self.branches)}, а сценарию нужен {n}-й")
        return self.branches[n - 1]

    def branch_of_district(self, district: str) -> BranchRef:
        """Филиал района помощника; в районе своего филиала нет — первый филиал."""
        return next((b for b in self.branches if b.district == district), self.branch(1))

    def item(self, code: str) -> ItemRef:
        found = self.catalog.get(code)
        if found is None:
            raise ScenarioError(f"Товара {code} нет в каталоге мира")
        return found


@dataclass(frozen=True)
class Home:
    district: str
    mahalla: str

    @property
    def registration(self) -> str:
        return f"{self.district}, {self.mahalla}"  # формат мира: «<район>, махалля N»


@dataclass(frozen=True)
class Place:
    address: str
    home: Home


@dataclass(frozen=True)
class CastPerson:
    pinfl: str
    phone: str
    device_id: str
    account: str
    place: Place | None
    employer_inn: str | None


@dataclass(frozen=True)
class CastCompany:
    inn: str
    account: str


@dataclass(frozen=True)
class Cast:
    """Участники одного запуска и общие идентификаторы по именам."""

    people: dict[str, CastPerson]
    companies: dict[str, CastCompany]
    phones: dict[str, str]
    devices: dict[str, str]
    places: dict[str, Place]


def run_seed(realm_id: UUID, number: int) -> str:
    return f"{realm_id}:{number}"


def _birth_date(rng: Random, years: tuple[int, int]) -> date:
    start, end = date(years[0], 1, 1), date(years[1], 12, 31)
    return start + timedelta(days=rng.randint(0, (end - start).days))


def _home(spec: HomeSpec | None, refs: WorldRefs, rng: Random) -> Home | None:
    if spec is None:
        return Home(*_pick_helper(refs, rng)) if refs.helpers else None
    helper = refs.helper(spec.helper)
    if spec.mahalla == "same":
        return Home(helper.district, helper.mahalla)
    others = sorted({h.mahalla for h in refs.helpers if h.district == helper.district} - {helper.mahalla})
    if not others:
        raise ScenarioError(f"В районе {helper.district} нет другой махалли")
    return Home(helper.district, others[rng.randrange(len(others))])


def _pick_helper(refs: WorldRefs, rng: Random) -> tuple[str, str]:
    helper = refs.helpers[rng.randrange(len(refs.helpers))]
    return helper.district, helper.mahalla


def _place(home: Home | None, refs: WorldRefs, rng: Random) -> Place | None:
    if home is None:
        return None
    house = rng.randint(*refs.house_numbers)
    return Place(refs.address_format.format(district=home.district, mahalla=home.mahalla, house=house), home)


def cast(spec: ScenarioSpec, refs: WorldRefs, rng: Random) -> Cast:
    ids = Identifiers(rng, list(refs.operator_codes))
    companies = {ref: CastCompany(inn=ids.legal_inn(), account=ids.account()) for ref in spec.companies}
    people: dict[str, CastPerson] = {}
    for ref, person in spec.people.items():
        born = _birth_date(rng, person.birth_years)
        people[ref] = CastPerson(
            pinfl=ids.pinfl(born, person.male, rng.randint(*refs.pinfl_district_codes)),
            phone=ids.phone(),
            device_id=ids.device(),
            account=ids.account(),
            place=_place(_home(person.home, refs, rng), refs, rng),
            employer_inn=None if person.employer is None else companies[person.employer].inn,
        )
    phones: dict[str, str] = {}
    devices: dict[str, str] = {}
    places: dict[str, Place] = {}
    for step in spec.steps:
        if not isinstance(step, ApplicationStep):
            continue
        if step.shared.phone is not None and step.shared.phone not in phones:
            phones[step.shared.phone] = ids.phone()
        if step.shared.device is not None and step.shared.device not in devices:
            devices[step.shared.device] = ids.device()
        if step.shared.address is not None and step.shared.address not in places:
            place = _place(_home(None, refs, rng), refs, rng)
            if place is None:
                raise ScenarioError("Общему адресу нужны справочники мира: сначала прогон мира")
            places[step.shared.address] = place
    return Cast(people=people, companies=companies, phones=phones, devices=devices, places=places)


def _branch(step: ApplicationStep, refs: WorldRefs, district: str | None) -> tuple[str, str | None]:
    if isinstance(step.branch, int):
        found = refs.branch(step.branch)
    elif step.branch == "online":
        return refs.online_branch, None
    elif district is None:
        raise ScenarioError("Филиал помощника — только для программной заявки")
    else:
        found = refs.branch_of_district(district)
    return found.id, found.employee_id


def _program(spec: ProgramSpec, cast_: Cast, refs: WorldRefs) -> dict[str, Any]:
    helper = refs.helper(spec.helper)
    item = refs.item(spec.item)
    supplier = cast_.companies[spec.supplier]
    return {
        "helper_id": helper.id,
        "supplier_inn": supplier.inn,
        "supplier_account": supplier.account,
        "item_code": spec.item,
        "unit": item.unit,
        "unit_price": round(item.median_price * spec.price_factor),
        "quantity": spec.quantity,
        "district": helper.district,
        "helper_mahalla": Home(helper.district, helper.mahalla).registration,
    }


def application_drafts(step: ApplicationStep, cast_: Cast, refs: WorldRefs) -> list[tuple[str, dict[str, Any]]]:
    """Черновики заявок шага в формате конвейера: (человек сценария, черновик)."""
    program = None if step.program is None else _program(step.program, cast_, refs)
    branch_id, employee_id = _branch(step, refs, None if program is None else str(program["district"]))
    amount = step.loan.amount if program is None else int(program["unit_price"]) * int(program["quantity"])
    drafts: list[tuple[str, dict[str, Any]]] = []
    for ref in step.people:
        person = cast_.people[ref]
        place = cast_.places[step.shared.address] if step.shared.address is not None else person.place
        applicant = {
            "pinfl": person.pinfl,
            "phone": cast_.phones[step.shared.phone] if step.shared.phone is not None else person.phone,
            "device_id": cast_.devices[step.shared.device] if step.shared.device is not None else person.device_id,
            "address": None if place is None else place.address,
            "employer_inn": person.employer_inn,
            "registration_mahalla": None if place is None else place.home.registration,
        }
        drafts.append(
            (
                ref,
                {
                    "channel": step.channel,
                    "branch_id": branch_id,
                    "employee_id": employee_id,
                    "applicant": applicant,
                    "loan": {"amount": amount, "term_months": step.loan.term_months},
                    "disbursement_account": person.account if step.channel == "online" else None,
                    "program": program,
                    "checks": {"biometry": "passed", "phone_owner_match": True},
                },
            )
        )
    return drafts
