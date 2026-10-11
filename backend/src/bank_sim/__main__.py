"""Команды имитатора банка: python -m bank_sim migrate | seed | revision "<сообщение>"."""

import sys
from pathlib import Path

from bank_sim.modules.personas import service as personas
from bank_sim.modules.staff import service as staff
from bank_sim.settings import BankEnv
from shared.db import Database
from shared.migrations import revision, upgrade

MIGRATIONS = Path(__file__).parent / "migrations"


def main(argv: list[str]) -> None:
    env = BankEnv()
    command = argv[0] if argv else ""
    if command == "migrate":
        upgrade(MIGRATIONS, env.database_url)
    elif command == "revision":
        revision(MIGRATIONS, env.database_url, argv[1])
    elif command == "seed":
        db = Database(env.database_url, pool_size=1)
        with db.transaction() as session:
            personas.seed(session, env.seeds_dir)
            staff.seed(session, env.seeds_dir)
        db.dispose()
    else:
        raise SystemExit("Команды: migrate | seed | revision <сообщение>")


if __name__ == "__main__":
    main(sys.argv[1:])
