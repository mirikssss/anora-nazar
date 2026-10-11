"""Настройки узла: секреты и адреса — из окружения (префикс NODE_), рабочие значения — из config/node.yaml."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from node.modules.risk.domain import RiskConfig
from shared.config import load_yaml

PACKAGE_DIR = Path(__file__).parent


class NodeEnv(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NODE_", extra="ignore")

    database_url: str
    signing_key_path: Path
    session_secret: str
    index_key: str
    bank_sim_url: str
    bank_sim_api_key: str
    anchor_url: str
    anchor_api_key: str
    network_url: str | None = None  # оператор сети кредиторов; не задан — сеть всегда «недоступна»
    network_api_key: str | None = None
    network_history_key: str | None = None
    log_level: str = "INFO"
    app_version: str | None = Field(default=None, validation_alias="APP_VERSION")  # коммит сборки, из образа
    demo_mode: bool = False  # вход без пароля — только в демо-режиме стенда (CLAUDE.md, «Роли и страницы»)
    training_in_process: bool = True  # False — обучение в отдельном процессе `python -m node trainer` (стенд)
    config_path: Path = PACKAGE_DIR / "config" / "node.yaml"
    policy_dir: Path = PACKAGE_DIR / "modules" / "policy" / "rules"
    seeds_dir: Path = PACKAGE_DIR / "seeds"
    scoring_config_path: Path = PACKAGE_DIR / "config" / "scoring.yaml"
    cases_config_path: Path = PACKAGE_DIR / "config" / "cases.yaml"
    verification_config_path: Path = PACKAGE_DIR / "config" / "verification.yaml"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PolicyConfig(_Frozen):
    active_version: str
    editable: list[str]


class PermitsConfig(_Frozen):
    reserve_ttl_seconds: int


class QueueConfig(_Frozen):
    max_lag_seconds: int
    watched_producers: list[str]


class IngestConfig(_Frozen):
    version_gap_timeout_seconds: int


class AuditConfig(_Frozen):
    checkpoint_interval_seconds: int


class RealmsConfig(_Frozen):
    sandbox_ttl_hours: int


class BackgroundConfig(_Frozen):
    tick_seconds: float


class Subscriber(_Frozen):
    name: str
    topics: list[str]


class OutboxConfig(_Frozen):
    batch_size: int
    subscribers: list[Subscriber]


class HttpConfig(_Frozen):
    timeout_seconds: float


class NetworkClientConfig(_Frozen):
    timeout_seconds: float


class DatabaseConfig(_Frozen):
    pool_size: int


class TextsConfig(_Frozen):
    active_catalog: str


class HistoryConfig(_Frozen):
    max_batch: int


class NodeConfig(_Frozen):
    version: str
    policy: PolicyConfig
    permits: PermitsConfig
    queue: QueueConfig
    ingest: IngestConfig
    audit: AuditConfig
    realms: RealmsConfig
    background: BackgroundConfig
    outbox: OutboxConfig
    history: HistoryConfig
    texts: TextsConfig
    risk: RiskConfig
    http: HttpConfig
    network: NetworkClientConfig
    database: DatabaseConfig


def load_config(path: Path) -> NodeConfig:
    return NodeConfig.model_validate(load_yaml(path))
