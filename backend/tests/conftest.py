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


@pytest.fixture(autouse=True)
def isolate_provider_cooldowns(monkeypatch):
    # Failure-path tests must not put unrelated later tests into cooldown.
    from app import providers
    monkeypatch.setattr(providers, '_PROVIDER_COOLDOWNS', {})


@pytest.fixture(autouse=True)
def isolate_rate_limits():
    from app.security import clear_rate_limits
    clear_rate_limits()
    yield
    clear_rate_limits()
