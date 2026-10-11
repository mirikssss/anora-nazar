"""Настройки имитатора: секреты и адреса — из окружения (BANK_SIM_), рабочие значения — config/bank_sim.yaml."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.config import load_yaml

PACKAGE_DIR = Path(__file__).parent


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
    log_level: str = "INFO"
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


def load_config(path: Path) -> BankConfig:
    return BankConfig.model_validate(load_yaml(path))
