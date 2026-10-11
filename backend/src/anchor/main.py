"""Точка входа якоря."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from anchor.context import AnchorContext
from anchor.routes import include_routers
from anchor.settings import AnchorEnv
from shared.clock import Clock, SystemClock
from shared.crypto.signing import read_public_key
from shared.db import Database
from shared.errors import install_error_handlers
from shared.logging import configure_logging


def build_context(env: AnchorEnv, clock: Clock) -> AnchorContext:
    return AnchorContext(
        env=env,
        db=Database(env.database_url, pool_size=5),
        clock=clock,
        verifier=read_public_key(env.node_public_key_path),
    )


def create_app(ctx: AnchorContext) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            ctx.db.dispose()

    app = FastAPI(title="Anora Nazar · якорь журнала", version="1.0", lifespan=lifespan)
    app.state.ctx = ctx
    install_error_handlers(app)
    include_routers(app)
    return app


def app_factory() -> FastAPI:
    env = AnchorEnv()
    configure_logging(env.log_level)
    return create_app(build_context(env, SystemClock()))
