"""Миграции базы имитатора банка."""

from bank_sim.model_registry import metadata
from shared.alembic_env import run

run(metadata)
