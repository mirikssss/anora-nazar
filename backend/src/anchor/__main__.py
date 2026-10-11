"""Команды якоря: python -m anchor migrate | revision "<сообщение>"."""

import sys
from pathlib import Path

from anchor.settings import AnchorEnv
from shared.migrations import revision, upgrade

MIGRATIONS = Path(__file__).parent / "migrations"


def main(argv: list[str]) -> None:
    env = AnchorEnv()
    command = argv[0] if argv else ""
    if command == "migrate":
        upgrade(MIGRATIONS, env.database_url)
    elif command == "revision":
        revision(MIGRATIONS, env.database_url, argv[1])
    else:
        raise SystemExit("Команды: migrate | revision <сообщение>")


if __name__ == "__main__":
    main(sys.argv[1:])
