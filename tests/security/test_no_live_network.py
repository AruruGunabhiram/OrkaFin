"""Regression checks for the suite-wide no-live-network gate."""

from __future__ import annotations

import socket
from collections.abc import Callable

import pytest


def test_outbound_socket_connections_are_blocked(
    live_network_guard_message: Callable[[], str],
) -> None:
    with pytest.raises(AssertionError, match="Live network access is forbidden") as error:
        socket.create_connection(("example.invalid", 443), timeout=0.01)

    assert str(error.value) == live_network_guard_message()
