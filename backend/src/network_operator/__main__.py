"""Команды оператора сети: python -m network_operator migrate | seed | revision "<сообщение>".

migrate создаёт базу оператора, если её нет: init.sql PostgreSQL выполняется только на пустом томе.
"""

import sys
from pathlib import Path

from network_operator.modules.clients import service as clients
from network_operator.settings import OperatorEnv
from shared.db import Database
from shared.migrations import ensure_database, revision, upgrade

MIGRATIONS = Path(__file__).parent / "migrations"


def main(argv: list[str]) -> None:
    env = OperatorEnv()
    command = argv[0] if argv else ""
    if command == "migrate":
        ensure_database(env.database_url)
        upgrade(MIGRATIONS, env.database_url)
    elif command == "seed":
        db = Database(env.database_url, pool_size=1)
        with db.transaction() as session:
            clients.seed(session, env.seeds_dir)
        db.dispose()
    elif command == "revision":
        revision(MIGRATIONS, env.database_url, argv[1])
    else:
        raise SystemExit("Команды: migrate | seed | revision <сообщение>")


if __name__ == "__main__":
    main(sys.argv[1:])
