"""Точка входа узла: API и фоновые задачи процесса."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from node.background import NodeTasks
from node.context import NodeContext
from node.model_registry import IDEMPOTENCY
from node.modules.policy.service import PolicyRegistry
from node.modules.scoring.service import ModelCache
from node.routes import include_routers
from node.settings import NodeEnv, load_config
from shared.clock import Clock, SystemClock
from shared.crypto.signing import Signer
from shared.db import Database
from shared.errors import install_error_handlers
from shared.http import ServiceClient
from shared.idempotency import IdempotencyStore
from shared.logging import configure_logging


def build_context(env: NodeEnv, clock: Clock) -> NodeContext:
    config = load_config(env.config_path)
    timeout = config.http.timeout_seconds
    return NodeContext(
        env=env,
        config=config,
        db=Database(env.database_url, pool_size=config.database.pool_size),
        clock=clock,
        signer=Signer.from_file(env.signing_key_path),
        policies=PolicyRegistry.from_dir(env.policy_dir, config.policy.active_version),
        idempotency=IdempotencyStore(IDEMPOTENCY),
        bank=ServiceClient(env.bank_sim_url, env.bank_sim_api_key, timeout_seconds=timeout, name="bank-sim"),
        anchor=ServiceClient(env.anchor_url, env.anchor_api_key, timeout_seconds=timeout, name="anchor"),
        models=ModelCache(),
    )


def create_app(ctx: NodeContext, *, run_background: bool) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        runner = NodeTasks(ctx).loop() if run_background else None
        if runner is not None:
            runner.start()
        try:
            yield
        finally:
            if runner is not None:
                runner.stop()
            ctx.bank.close()
            ctx.anchor.close()
            ctx.db.dispose()

    app = FastAPI(title="Anora Nazar · узел", version="1.0", lifespan=lifespan)
    app.state.ctx = ctx
    install_error_handlers(app)
    include_routers(app)
    return app


def app_factory() -> FastAPI:
    env = NodeEnv()
    configure_logging(env.log_level)
    return create_app(build_context(env, SystemClock()), run_background=True)
