import socket

import pytest


@pytest.fixture(scope="session", autouse=True)
def block_network():
    """Prevent real network access during the test suite."""
    original_socket = socket.socket

    def blocked_socket(*args, **kwargs):
        raise RuntimeError("Network access is forbidden in unit tests")

    socket.socket = blocked_socket

    try:
        yield
    finally:
        socket.socket = original_socket