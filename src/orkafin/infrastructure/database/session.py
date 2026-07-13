"""Database construction and FastAPI session dependency."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, event
from sqlalchemy.engine import create_engine
from sqlalchemy.orm import Session, sessionmaker


class Database:
    """Owns an engine and explicit SQLAlchemy session factory."""

    def __init__(self, url: str) -> None:
        self.engine: Engine = create_engine(url)
        if url.startswith("sqlite"):
            event.listen(self.engine, "connect", _enable_sqlite_foreign_keys)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def session_dependency(self) -> Generator[Session, None, None]:
        """FastAPI-compatible dependency callable bound to this database instance."""
        yield from get_database_session(self)


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _: object) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_database_session(database: Database) -> Generator[Session, None, None]:
    """Yield one transaction-neutral session for a request or application service."""
    with database.session_factory() as session:
        yield session
