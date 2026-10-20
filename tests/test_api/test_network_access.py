"""Tests for the client network allowlist."""

import ipaddress
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from asterisk_phone_management.api.network_access import (
    ClientNetworkMiddleware,
    configure_network_access,
    is_allowed,
    parse_networks,
)
from asterisk_phone_management.core.exceptions import AsteriskCliError

ALLOWED = (ipaddress.ip_network("10.20.0.0/24"),)


def _app() -> FastAPI:
    """Build a tiny app with one HTTP route and one websocket.

    Returns:
        The app, wrapped in the allowlist middleware.
    """
    app = FastAPI()

    @app.get("/ping")
    def ping() -> str:
        """Return a fixed response."""
        return "pong"

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        """Accept, send one message, and close."""
        await websocket.accept()
        await websocket.send_text("hello")
        await websocket.close()

    app.add_middleware(ClientNetworkMiddleware, networks=ALLOWED)
    return app


def test_parse_networks_reads_entries() -> None:
    """Entries are trimmed, blanks skipped, and bare hosts accepted."""
    assert parse_networks(" 10.20.0.0/24, ,127.0.0.1 ") == (
        ipaddress.ip_network("10.20.0.0/24"),
        ipaddress.ip_network("127.0.0.1/32"),
    )


def test_parse_networks_empty() -> None:
    """An empty string means no allowlist."""
    assert parse_networks("") == ()


def test_parse_networks_rejects_invalid_entry() -> None:
    """A typo fails loudly instead of silently allowing everyone."""
    with pytest.raises(AsteriskCliError, match="not-a-network"):
        parse_networks("10.20.0.0/24, not-a-network")


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("10.20.0.5", True),
        ("::ffff:10.20.0.5", True),
        ("10.20.1.5", False),
        ("2001:db8::1", False),
        ("testclient", False),
        (None, False),
    ],
)
def test_is_allowed(host: str | None, expected: bool) -> None:
    """Addresses are matched by network; non-addresses are refused."""
    assert is_allowed(host, ALLOWED) is expected


def test_http_from_allowed_network_passes() -> None:
    """Clients inside the allowlist reach the route."""
    client = TestClient(_app(), client=("10.20.0.5", 50000))
    assert client.get("/ping").status_code == 200


def test_http_from_other_network_is_forbidden() -> None:
    """Clients outside the allowlist get 403."""
    client = TestClient(_app(), client=("192.168.1.10", 50000))
    response = client.get("/ping")
    assert response.status_code == 403
    assert response.text == "Forbidden"


def test_websocket_from_allowed_network_passes() -> None:
    """Allowed clients can open a websocket."""
    client = TestClient(_app(), client=("10.20.0.5", 50000))
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_text() == "hello"


def test_websocket_from_other_network_is_rejected() -> None:
    """Websockets from outside the allowlist are closed before accept."""
    client = TestClient(_app(), client=("192.168.1.10", 50000))
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/ws"),
    ):
        pass


async def test_non_http_scopes_pass_through() -> None:
    """Lifespan and other scope types are not filtered."""
    inner = AsyncMock()
    receive = AsyncMock()
    send = AsyncMock()
    middleware = ClientNetworkMiddleware(inner, networks=ALLOWED)
    await middleware({"type": "lifespan"}, receive, send)
    inner.assert_awaited_once_with({"type": "lifespan"}, receive, send)


def test_configure_network_access_installs_middleware() -> None:
    """A configured allowlist adds the middleware."""
    app = FastAPI()
    configure_network_access(app, "10.20.0.0/24")
    assert any(m.cls is ClientNetworkMiddleware for m in app.user_middleware)


def test_configure_network_access_warns_when_unset(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """With no allowlist, nothing is installed and a warning is logged."""
    monkeypatch.delenv("ASTERISK_CLI_ALLOWED_NETWORKS", raising=False)
    app = FastAPI()
    configure_network_access(app)
    assert app.user_middleware == []
    assert "is not set" in caplog.text
