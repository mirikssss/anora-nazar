"""Настройки оператора сети: секреты и адреса — из окружения (OPERATOR_), рабочие значения — config/operator.yaml."""

import re
from datetime import timedelta
from pathlib import Path
from typing import Self, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.config import load_yaml
from shared.contracts.network import TOKEN_KINDS, CounterName, TokenKind

PACKAGE_DIR = Path(__file__).parent
SEED_BYTES = 32
DURATION = re.compile(r"(?P<amount>[1-9][0-9]*)(?P<unit>[hd])")
UNIT_SECONDS = {"h": 3600, "d": 86400}


class OperatorEnv(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPERATOR_", extra="ignore")

    database_url: str
    oprf_seed: str = Field(description="Секрет ключей OPRF: 32 байта в hex")
    demo_mode: bool = False
    log_level: str = "INFO"
    app_version: str | None = Field(default=None, validation_alias="APP_VERSION")  # коммит сборки, из образа
    config_path: Path = PACKAGE_DIR / "config" / "operator.yaml"
    seeds_dir: Path = PACKAGE_DIR / "seeds"

    @field_validator("oprf_seed")
    @classmethod
    def _seed(cls, value: str) -> str:
        try:
            raw = bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError("OPERATOR_OPRF_SEED — hex") from exc
        if len(raw) != SEED_BYTES:
            raise ValueError(f"OPERATOR_OPRF_SEED — {SEED_BYTES} байта")
        return value

    @property
    def seed(self) -> bytes:
        return bytes.fromhex(self.oprf_seed)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def parse_duration(text: str) -> timedelta:
    """Окно вида 1h, 24h, 7d, 30d."""
    found = DURATION.fullmatch(text)
    if found is None:
        raise ValueError(f"Окно «{text}» — число и h или d")
    return timedelta(seconds=int(found["amount"]) * UNIT_SECONDS[found["unit"]])


class OprfConfig(_Frozen):
    key_versions: dict[TokenKind, int]

    @model_validator(mode="after")
    def _all_kinds(self) -> Self:
        missing = set(TOKEN_KINDS) - set(self.key_versions)
        if missing or any(v < 1 for v in self.key_versions.values()):
            raise ValueError(f"Версия ключа ≥ 1 нужна для каждого типа; нет: {sorted(missing)}")
        return self


class CountersConfig(_Frozen):
    windows: dict[CounterName, str]

    @model_validator(mode="after")
    def _windows_match_names(self) -> Self:
        names: tuple[str, ...] = get_args(CounterName)
        if set(self.windows) != set(names):
            raise ValueError("Окна нужны ровно для счётчиков контракта")
        for name, window in self.windows.items():
            if parse_duration(window) != parse_duration(name.rsplit("_", 1)[1]):
                raise ValueError(f"Окно счётчика {name} — {window}: имя фиксирует окно, смена окна — новый контракт")
        return self

    def durations(self) -> dict[CounterName, timedelta]:
        return {name: parse_duration(window) for name, window in self.windows.items()}


class QuotasConfig(_Frozen):
    window_seconds: int = Field(gt=0)
    reserve: int = Field(ge=0)
    per_application: int = Field(ge=0)


class WatchesConfig(_Frozen):
    max_seconds: int = Field(gt=0)


class NotificationsConfig(_Frozen):
    tick_seconds: float = Field(gt=0)
    batch_size: int = Field(gt=0)
    retry_seconds: int = Field(gt=0)
    max_attempts: int = Field(gt=0)
    timeout_seconds: float = Field(gt=0)


class DatabaseConfig(_Frozen):
    pool_size: int = Field(gt=0)


class OperatorConfig(_Frozen):
    version: str
    oprf: OprfConfig
    counters: CountersConfig
    quotas: QuotasConfig
    watches: WatchesConfig
    notifications: NotificationsConfig
    database: DatabaseConfig


def load_config(path: Path) -> OperatorConfig:
    return OperatorConfig.model_validate(load_yaml(path))
