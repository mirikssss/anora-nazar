"""Фоновые задачи сервиса: работает один ведущий процесс, он держит advisory lock на отдельном соединении."""

import logging
import threading
from collections.abc import Callable, Sequence

from sqlalchemy import text

from shared.db import Database

log = logging.getLogger(__name__)

Task = tuple[str, Callable[[], object]]


class LeaderLoop:
    def __init__(self, db: Database, lock_key: int, tick_seconds: float, tasks: Sequence[Task], name: str) -> None:
        self._db = db
        self._lock_key = lock_key
        self._tick = tick_seconds
        self._tasks = tasks
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=10)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                with self._db.engine.connect() as conn:
                    if conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": self._lock_key}).scalar():
                        try:
                            self._lead()
                        finally:
                            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": self._lock_key})
            except Exception:
                log.exception("фоновые задачи: потеряно соединение с базой")
            self._stop.wait(self._tick)

    def _lead(self) -> None:
        while not self._stop.is_set():
            self.run_once()
            self._stop.wait(self._tick)

    def run_once(self) -> None:
        """Один такт всех задач; ошибка одной задачи не останавливает остальные."""
        for name, task in self._tasks:
            try:
                task()
            except Exception:
                log.exception("фоновая задача %s завершилась ошибкой", name)
