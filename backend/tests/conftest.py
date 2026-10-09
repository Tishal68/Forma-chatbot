"""Backend regression tests must never contact a live provider."""
import socket

import pytest


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise RuntimeError('Network disabled in tests; use MockTransport or an in-process client.')

    monkeypatch.setattr(socket, 'create_connection', blocked)
    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket.socket, 'connect_ex', blocked)
