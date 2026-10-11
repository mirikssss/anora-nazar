"""Общий env.py для Alembic: миграции в режиме online по URL из конфигурации."""

from alembic import context
from sqlalchemy import MetaData, engine_from_config, pool


def run(target_metadata: MetaData) -> None:
    config = context.config
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
