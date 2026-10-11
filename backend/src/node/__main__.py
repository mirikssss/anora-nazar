"""Команды узла: python -m node migrate | seed | revision "<сообщение>"."""

import sys
from pathlib import Path

from node.modules.identity import service as identity
from node.modules.realms import service as realms
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
    else:
        raise SystemExit("Команды: migrate | seed | revision <сообщение>")


if __name__ == "__main__":
    main(sys.argv[1:])
