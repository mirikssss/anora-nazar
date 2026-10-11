"""Миграции базы узла."""

from node.model_registry import metadata
from shared.alembic_env import run

run(metadata)
