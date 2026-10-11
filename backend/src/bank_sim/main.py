"""Точка входа имитатора банка: API и фоновые задачи процесса."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from bank_sim.background import BankTasks
from bank_sim.context import BankContext
from bank_sim.node_gateway import NodeGateway
from bank_sim.routes import include_routers
from bank_sim.settings import BankEnv, load_config
from shared.clock import Clock, SystemClock
from shared.crypto.signing import read_public_key
from shared.db import Database
from shared.errors import install_error_handlers
from shared.logging import configure_logging


def build_context(env: BankEnv, clock: Clock, node_transport: httpx.BaseTransport | None = None) -> BankContext:
    config = load_config(env.config_path)
    return BankContext(
        env=env,
        config=config,
        db=Database(env.database_url, pool_size=config.database.pool_size),
        clock=clock,
        node=NodeGateway(env, config.http.timeout_seconds, node_transport),
        node_verifier=read_public_key(env.node_public_key_path),
    )


def create_app(ctx: BankContext, *, run_background: bool) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        loop = BankTasks(ctx).loop() if run_background else None
        if loop is not None:
            loop.start()
        try:
            yield
        finally:
            if loop is not None:
                loop.stop()
            ctx.node.close()
            ctx.db.dispose()

    app = FastAPI(title="Anora Nazar · имитатор банка", version="1.0", lifespan=lifespan)
    app.state.ctx = ctx
    install_error_handlers(app)
    include_routers(app)
    return app


def app_factory() -> FastAPI:
    env = BankEnv()
    configure_logging(env.log_level)
    return create_app(build_context(env, SystemClock()), run_background=True)
