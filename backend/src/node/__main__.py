"""Команды узла: python -m node migrate | seed | revision "<сообщение>" | train [--release-by A --approve-by B]
| trainer.

trainer — отдельный процесс очереди обучения: долгое обучение не делит CPU с решениями API (стенд).

train обучает модели на общем мире и пишет отчёт качества; с двумя сотрудниками-подписантами — сразу выпускает
новые версии в общий мир (запрос и подтверждение разными людьми, как в API).
"""

import argparse
import json
import sys
from pathlib import Path

from node.background import NodeTasks
from node.main import build_context
from node.modules.identity import service as identity
from node.modules.realms import service as realms
from node.modules.scoring.training import pipeline, release
from node.modules.scoring.training.config import load_training_config
from node.settings import NodeEnv
from shared.clock import SystemClock
from shared.db import Database
from shared.migrations import revision, upgrade

MIGRATIONS = Path(__file__).parent / "migrations"


def main(argv: list[str]) -> None:
    env = NodeEnv()
    command = argv[0] if argv else ""
    if command == "migrate":
        upgrade(MIGRATIONS, env.database_url)
    elif command == "revision":
        revision(MIGRATIONS, env.database_url, argv[1])
    elif command == "seed":
        db = Database(env.database_url, pool_size=1)
        with db.transaction() as session:
            realms.ensure_world(session, SystemClock().now())
            identity.seed(session, env.seeds_dir)
        db.dispose()
    elif command == "train":
        train(env, argv[1:])
    elif command == "trainer":
        NodeTasks(build_context(env, SystemClock())).training_loop().run_forever()
    else:
        raise SystemExit(
            "Команды: migrate | seed | revision <сообщение> | train [--release-by A --approve-by B] | trainer"
        )


def train(env: NodeEnv, argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="python -m node train")
    parser.add_argument("--release-by")
    parser.add_argument("--approve-by")
    args = parser.parse_args(argv)
    ctx = build_context(env, SystemClock())
    cfg = load_training_config(env.scoring_config_path)
    now = ctx.clock.now()
    with ctx.db.transaction() as session:
        world = realms.resolve(session, realms.world_id(session), now)
        result = pipeline.run(session, world, cfg, ctx.policies.active.policy, ctx.index_key, now, ctx.network())
        if args.release_by and args.approve_by:
            for code in (args.release_by, args.approve_by):
                identity.require_staff_permission(session, code, "models.promote")
            for version in result.versions:
                requested = release.request(session, world.id, version.id, args.release_by, now)
                release.approve(session, world.id, requested.id, args.approve_by, now)
    for summary in result.report["models"]:
        print(json.dumps(summary, ensure_ascii=False, default=str))
    ctx.db.dispose()


if __name__ == "__main__":
    main(sys.argv[1:])
