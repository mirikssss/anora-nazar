"""Команды имитатора банка: python -m bank_sim migrate | seed | revision "<сообщение>" | world [--scale X].

world генерирует синтетический мир, кладёт его персонал в базу имитатора, отправляет события кредиторов Б и В
в сеть кредиторов и прогоняет историю банка A через узел. События Б и В идут первыми: тогда счётчики сети на
прошлые моменты, которые узел считает при обучении, честные.
"""

import argparse
import sys
from pathlib import Path

from bank_sim.modules.history_replay import service as history
from bank_sim.modules.lenders import service as lenders
from bank_sim.modules.personas import service as personas
from bank_sim.modules.staff import service as staff
from bank_sim.network_gateway import NetworkGateway
from bank_sim.node_gateway import NodeGateway
from bank_sim.settings import BankConfig, BankEnv, load_config
from shared.db import Database
from shared.migrations import revision, upgrade
from world import World, generate
from world.config import load_params

MIGRATIONS = Path(__file__).parent / "migrations"
PACKAGES_DIR = Path(__file__).parents[1]


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
    elif command == "world":
        build_world(env, argv[1:])
    else:
        raise SystemExit("Команды: migrate | seed | revision <сообщение> | world [--scale X] [--without-network]")


def build_world(env: BankEnv, argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="python -m bank_sim world")
    parser.add_argument("--scale", type=float, default=None)
    parser.add_argument("--staff-only", action="store_true", help="только справочники персонала мира, без прогона")
    parser.add_argument("--without-network", action="store_true", help="не отправлять события кредиторов Б и В в сеть")
    args = parser.parse_args(argv)
    config = load_config(env.config_path)
    params = load_params(PACKAGES_DIR / config.history.params_path, args.scale)
    world = generate(params)
    db = Database(env.database_url, pool_size=1)
    with db.transaction() as session:
        history.store_staff(session, world)
    db.dispose()
    if args.staff_only:
        return
    if not args.without_network:
        replay_lenders(env, config, world)
    gateway = NodeGateway(env, config.http.timeout_seconds)
    client = gateway.history(config.history.timeout_seconds)
    try:
        outcomes = history.replay(
            client, world, config.history.batch_size, lambda done, total: print(f"{done}/{total}", flush=True)
        )
    finally:
        client.close()
        gateway.close()
    print(dict(outcomes))


def replay_lenders(env: BankEnv, config: BankConfig, world: World) -> None:
    network = NetworkGateway.from_env(env, config.http.timeout_seconds)
    if network is None:
        print("Сеть кредиторов не настроена (BANK_SIM_NETWORK_URL): события кредиторов Б и В пропущены", flush=True)
        return
    try:
        summary = lenders.replay_history(
            network, world, config.lenders, lambda code, done, total: print(f"{code}: {done}/{total}", flush=True)
        )
    finally:
        network.close()
    print({code: dict(totals) for code, totals in summary.items()}, flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
