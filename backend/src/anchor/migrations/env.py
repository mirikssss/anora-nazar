"""Миграции базы якоря."""

from anchor.model_registry import metadata
from shared.alembic_env import run

run(metadata)
