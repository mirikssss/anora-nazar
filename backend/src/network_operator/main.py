"""Точка входа оператора сети: API и фоновая доставка уведомлений."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from network_operator.background import OperatorTasks
from network_operator.callbacks import CallbackSender
from network_operator.context import OperatorContext
from network_operator.modules.clients import service as clients
from network_operator.modules.oprf.domain import KeyRing
from network_operator.routes import include_routers
from network_operator.settings import OperatorEnv, load_config
from shared.clock import Clock, SystemClock
from shared.db import Database
from shared.errors import install_error_handlers
from shared.logging import configure_logging


def build_context(
    env: OperatorEnv, clock: Clock, callback_transport: httpx.BaseTransport | None = None
) -> OperatorContext:
    config = load_config(env.config_path)
    return OperatorContext(
        env=env,
        config=config,
        db=Database(env.database_url, pool_size=config.database.pool_size),
        clock=clock,
        keys=KeyRing(env.seed, config.oprf.key_versions),
        callbacks=CallbackSender(
            clients.callbacks(env.seeds_dir), config.notifications.timeout_seconds, callback_transport
        ),
    )


def create_app(ctx: OperatorContext, *, run_background: bool) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        loop = OperatorTasks(ctx).loop() if run_background else None
        if loop is not None:
            loop.start()
        try:
            yield
        finally:
            if loop is not None:
                loop.stop()
            ctx.callbacks.close()
            ctx.db.dispose()

    app = FastAPI(title="Anora Nazar · оператор сети кредиторов", version="1.0", lifespan=lifespan)
    app.state.ctx = ctx
    install_error_handlers(app)
    include_routers(app)
    return app


def app_factory() -> FastAPI:
    env = OperatorEnv()
    configure_logging(env.log_level)
    return create_app(build_context(env, SystemClock()), run_background=True)
