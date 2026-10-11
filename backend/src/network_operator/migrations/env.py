"""Миграции базы оператора сети."""

from network_operator.model_registry import metadata
from shared.alembic_env import run

run(metadata)
