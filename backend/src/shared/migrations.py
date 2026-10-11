"""Миграции Alembic без alembic.ini: у каждого сервиса своя папка миграций и своя база."""

import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from shared.errors import ConfigurationError

MAINTENANCE_DATABASE = "postgres"
DATABASE_NAME = re.compile(r"[a-z_][a-z0-9_]*")


def _config(script_location: Path, url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def upgrade(script_location: Path, url: str) -> None:
    command.upgrade(_config(script_location, url), "head")


def revision(script_location: Path, url: str, message: str) -> None:
    command.revision(_config(script_location, url), message=message, autogenerate=True)


def ensure_database(url: str) -> None:
    """Создаёт базу сервиса, если её нет: init.sql выполняется только на пустом томе PostgreSQL."""
    target = make_url(url)
    name = target.database or ""
    if not DATABASE_NAME.fullmatch(name):
        raise ConfigurationError(f"Имя базы «{name}» не подходит: строчные латинские буквы, цифры и _")
    admin = create_engine(target.set(database=MAINTENANCE_DATABASE), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            if conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}).scalar() is None:
                conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        admin.dispose()
