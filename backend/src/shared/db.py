"""PostgreSQL: движок, фабрика сессий, транзакция на запрос, повтор при взаимной блокировке."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TypeVar

from psycopg import errors as pg_errors
from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

T = TypeVar("T")


def make_metadata() -> MetaData:
    return MetaData(naming_convention=NAMING_CONVENTION)


class Database:
    """Движок и сессии одного сервиса. Транзакция = одна единица работы."""

    def __init__(self, url: str, *, pool_size: int = 10) -> None:
        self.engine: Engine = create_engine(url, pool_size=pool_size, pool_pre_ping=True, future=True)
        self._sessions = sessionmaker(bind=self.engine, expire_on_commit=False, autoflush=False)

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        session = self._sessions()
        try:
            with session.begin():
                yield session
        finally:
            session.close()

    def run(self, work: Callable[[Session], T], *, attempts: int = 3) -> T:
        """Выполняет работу в транзакции; при взаимной блокировке PostgreSQL повторяет её целиком."""
        for attempt in range(1, attempts + 1):
            try:
                with self.transaction() as session:
                    return work(session)
            except DBAPIError as exc:
                retriable = isinstance(exc.orig, pg_errors.DeadlockDetected | pg_errors.SerializationFailure)
                if not retriable or attempt == attempts:
                    raise
        raise AssertionError("недостижимо")

    def dispose(self) -> None:
        self.engine.dispose()
