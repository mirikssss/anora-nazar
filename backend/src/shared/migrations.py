"""Миграции Alembic без alembic.ini: у каждого сервиса своя папка миграций и своя база."""

from pathlib import Path

from alembic import command
from alembic.config import Config


def _config(script_location: Path, url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def upgrade(script_location: Path, url: str) -> None:
    command.upgrade(_config(script_location, url), "head")


def revision(script_location: Path, url: str, message: str) -> None:
    command.revision(_config(script_location, url), message=message, autogenerate=True)
