"""Настройки имитатора: секреты и адреса — из окружения (BANK_SIM_), рабочие значения — config/bank_sim.yaml."""

from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bank_sim.modules.borrower_app.domain import ScreenRules
from bank_sim.modules.transfers.domain import OwnRule
from shared.config import load_yaml

PACKAGE_DIR = Path(__file__).parent
PACKAGES_DIR = PACKAGE_DIR.parent  # корень пакетов backend/src: от него — путь к параметрам мира


class BankEnv(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BANK_SIM_", extra="ignore")

    database_url: str
    node_url: str
    node_key_conveyor: str
    node_key_core_banking: str
    node_key_events: str
    node_key_realms: str
    node_key_history: str | None = None  # нужен только команде прогона мира
    node_public_key_path: Path
    api_key_node: str
    # Сеть кредиторов: без адреса оператора кредиторы Б и В молчат, сценарии с ними не запускаются
    network_url: str | None = None
    network_key_b: str | None = None
    network_key_c: str | None = None
    network_key_b_history: str | None = None  # нужны только команде прогона мира
    network_key_c_history: str | None = None
    network_key_admin: str | None = None  # удаление контура песочницы и сбой «сеть недоступна»
    log_level: str = "INFO"
    app_version: str | None = Field(default=None, validation_alias="APP_VERSION")  # коммит сборки, из образа
    cookie_secure: bool = False  # True на стенде по HTTPS: cookie песочницы только по защищённому соединению
    config_path: Path = PACKAGE_DIR / "config" / "bank_sim.yaml"
    seeds_dir: Path = PACKAGE_DIR / "seeds"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BureauConfig(_Frozen):
    lock_hours: int


class SandboxesConfig(_Frozen):
    ttl_hours: int


class BackgroundConfig(_Frozen):
    tick_seconds: float
    watermark_interval_seconds: float


class OutboxConfig(_Frozen):
    batch_size: int


class HttpConfig(_Frozen):
    timeout_seconds: float


class DatabaseConfig(_Frozen):
    pool_size: int


class HistoryConfig(_Frozen):
    params_path: str
    batch_size: int
    timeout_seconds: float


class CardsConfig(_Frozen):
    opening_balance: int = Field(ge=0)


class TransfersConfig(_Frozen):
    own_rule: OwnRule


class AmountRange(_Frozen):
    min: int = Field(gt=0)
    max: int = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.min > self.max:
            raise ValueError("Нижняя граница суммы больше верхней")
        return self


class BorrowerConfig(_Frozen):
    branch_id: str = Field(min_length=1)
    amount: AmountRange
    terms_months: list[int] = Field(min_length=1)
    screens: ScreenRules


class ScenariosConfig(_Frozen):
    pinfl_district_codes: tuple[int, int]
    house_numbers: tuple[int, int]
    card_prefixes: list[str] = Field(min_length=1)


class LendersConfig(_Frozen):
    delivery_delay_seconds: int = Field(ge=0)
    history_chunk: int = Field(gt=0)
    timeout_seconds: float = Field(gt=0)


class BankConfig(_Frozen):
    version: str
    producer: str
    bureau: BureauConfig
    sandboxes: SandboxesConfig
    background: BackgroundConfig
    outbox: OutboxConfig
    http: HttpConfig
    database: DatabaseConfig
    history: HistoryConfig
    cards: CardsConfig
    transfers: TransfersConfig
    borrower: BorrowerConfig
    scenarios: ScenariosConfig
    lenders: LendersConfig

    @property
    def world_params_path(self) -> Path:
        return PACKAGES_DIR / self.history.params_path


def load_config(path: Path) -> BankConfig:
    return BankConfig.model_validate(load_yaml(path))
