"""Global test safety gates."""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from orkafin.infrastructure.database.session import Database

_NO_LIVE_NETWORK_MESSAGE = (
    "Live network access is forbidden in the OrkaFin test suite; inject an in-process transport."
)


@pytest.fixture(autouse=True)
def block_live_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail every outbound socket connection while allowing in-process ASGI transports."""

    def blocked(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise AssertionError(_NO_LIVE_NETWORK_MESSAGE)

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket.socket, "sendto", blocked)
    if hasattr(socket.socket, "sendmsg"):
        monkeypatch.setattr(socket.socket, "sendmsg", blocked)
    yield


@pytest.fixture(autouse=True)
def dispose_test_databases(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Dispose every test-created SQLAlchemy engine after dependent fixtures tear down."""
    databases: list[Database] = []
    original_init = Database.__init__

    def tracked_init(database: Database, url: str) -> None:
        original_init(database, url)
        databases.append(database)

    monkeypatch.setattr(Database, "__init__", tracked_init)
    yield
    for database in reversed(databases):
        database.engine.dispose()


@pytest.fixture()
def live_network_guard_message() -> Callable[[], str]:
    """Expose only the stable assertion text to the guard's own regression test."""
    return lambda: _NO_LIVE_NETWORK_MESSAGE
