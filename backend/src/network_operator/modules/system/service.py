"""Здоровье оператора."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def database_alive(session: Session) -> bool:
    return session.execute(text("SELECT 1")).scalar() == 1
