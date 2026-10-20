"""Tests for optional shared-login authentication."""

import base64
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from asterisk_phone_management.api.auth import (
    BasicAuthMiddleware,
    BasicCredentials,
    check_authorization,
    configure_auth,
    load_credentials,
    parse_auth_mode,
)
from asterisk_phone_management.api.network_access import (
    configure_network_access,
)
from asterisk_phone_management.core.exceptions import AsteriskCliError

CREDS = BasicCredentials(username="helpdesk", password="s3cret:with:colons")


def _basic(username: str, password: str) -> str:
    """Encode a Basic ``Authorization`` header value.

    Args:
        username: The username to encode.
        password: The password to encode.

    Returns:
        The header value.
    """
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


GOOD = {"Authorization": _basic(CREDS.username, CREDS.password)}


def _app() -> FastAPI:
    """Build a tiny app with one HTTP route and one websocket.

    Returns:
        The app, without any middleware installed.
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

    return app


def _protected() -> TestClient:
    """Return a client for an app that requires the shared login.

    Returns:
        A test client for the protected app.
    """
    app = _app()
    app.add_middleware(BasicAuthMiddleware, credentials=CREDS)
    return TestClient(app)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "none"),
        ("", "none"),
        ("none", "none"),
        (" Basic ", "basic"),
    ],
)
def test_parse_auth_mode(raw: str | None, expected: str) -> None:
    """Unset means none; values are trimmed and case-insensitive."""
    assert parse_auth_mode(raw) == expected


def test_parse_auth_mode_rejects_unknown() -> None:
    """A typo fails at startup instead of silently disabling auth."""
    with pytest.raises(AsteriskCliError, match="'none' or 'basic'"):
        parse_auth_mode("something else")


@pytest.mark.parametrize(
    ("username", "password", "missing"),
    [
        (None, "pw", "ASTERISK_CLI_WEB_USER"),
        ("  ", "pw", "ASTERISK_CLI_WEB_USER"),
        ("user", None, "ASTERISK_CLI_WEB_PASSWORD"),
        ("user", "", "ASTERISK_CLI_WEB_PASSWORD"),
        (None, None, "ASTERISK_CLI_WEB_USER and ASTERISK_CLI_WEB_PASSWORD"),
    ],
)
def test_load_credentials_requires_both(
    username: str | None, password: str | None, missing: str
) -> None:
    """Basic mode refuses to start without a username and password."""
    with pytest.raises(AsteriskCliError, match=missing):
        load_credentials(username, password)


def test_load_credentials_trims_username() -> None:
    """Whitespace around the username is ignored; the password is not."""
    assert load_credentials(" user ", " pw ") == BasicCredentials(
        username="user", password=" pw "
    )


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (_basic("helpdesk", "s3cret:with:colons"), True),
        (_basic("helpdesk", "wrong"), False),
        (_basic("someone", "s3cret:with:colons"), False),
        (None, False),
        ("Bearer abc", False),
        ("Basic", False),
        ("Basic !!!not-base64!!!", False),
        ("Basic " + base64.b64encode(b"\xff\xfe").decode(), False),
        ("Basic " + base64.b64encode(b"no-colon").decode(), False),
    ],
)
def test_check_authorization(header: str | None, expected: bool) -> None:
    """Only a well-formed header with the right login is accepted."""
    assert check_authorization(header, CREDS) is expected


def test_http_without_login_is_challenged() -> None:
    """Missing credentials get 401 with a Basic challenge."""
    response = _protected().get("/ping")
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Basic ")


def test_http_with_wrong_login_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Wrong credentials get 401 and a log entry without the password."""
    response = _protected().get(
        "/ping", headers={"Authorization": _basic("helpdesk", "nope")}
    )
    assert response.status_code == 401
    assert "Failed login" in caplog.text
    assert "nope" not in caplog.text


def test_http_with_login_passes() -> None:
    """The right credentials reach the route."""
    assert _protected().get("/ping", headers=GOOD).status_code == 200


def test_websocket_with_login_passes() -> None:
    """Browsers resend the login on the websocket handshake."""
    with _protected().websocket_connect("/ws", headers=GOOD) as websocket:
        assert websocket.receive_text() == "hello"


def test_websocket_without_login_is_rejected() -> None:
    """Websockets without the login are closed before accept."""
    with (
        pytest.raises(WebSocketDisconnect),
        _protected().websocket_connect("/ws"),
    ):
        pass


async def test_non_http_scopes_pass_through() -> None:
    """Lifespan and other scope types are not challenged."""
    inner = AsyncMock()
    receive = AsyncMock()
    send = AsyncMock()
    middleware = BasicAuthMiddleware(inner, credentials=CREDS)
    await middleware({"type": "lifespan"}, receive, send)
    inner.assert_awaited_once_with({"type": "lifespan"}, receive, send)


def test_configure_auth_none_installs_nothing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """With auth off, no middleware is added and a warning is logged."""
    monkeypatch.delenv("ASTERISK_CLI_WEB_AUTH", raising=False)
    app = FastAPI()
    assert configure_auth(app) == "none"
    assert app.user_middleware == []
    assert "disabled" in caplog.text


def test_configure_auth_basic_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Basic mode reads the login from the environment."""
    monkeypatch.setenv("ASTERISK_CLI_WEB_AUTH", "basic")
    monkeypatch.setenv("ASTERISK_CLI_WEB_USER", "helpdesk")
    monkeypatch.setenv("ASTERISK_CLI_WEB_PASSWORD", "pw")
    app = FastAPI()
    assert configure_auth(app) == "basic"
    assert any(m.cls is BasicAuthMiddleware for m in app.user_middleware)


def test_configure_auth_basic_from_arguments() -> None:
    """Explicit arguments override the environment."""
    app = _app()
    configure_auth(app, mode="basic", username="u", password="p")
    client = TestClient(app)
    assert client.get("/ping").status_code == 401
    assert (
        client.get("/ping", headers={"Authorization": _basic("u", "p")})
    ).status_code == 200


def test_network_check_runs_before_login() -> None:
    """Outside clients get 403 even with a valid login."""
    app = _app()
    configure_auth(app, mode="basic", username="u", password="p")
    configure_network_access(app, "10.20.0.0/24")
    login = {"Authorization": _basic("u", "p")}

    outside = TestClient(app, client=("192.168.1.10", 50000))
    assert outside.get("/ping", headers=login).status_code == 403

    inside = TestClient(app, client=("10.20.0.5", 50000))
    assert inside.get("/ping").status_code == 401
    assert inside.get("/ping", headers=login).status_code == 200
