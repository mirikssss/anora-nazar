"""Настройки якоря из окружения (префикс ANCHOR_)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AnchorEnv(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ANCHOR_", extra="ignore")

    database_url: str
    node_public_key_path: Path
    api_key_node: str
    log_level: str = "INFO"
