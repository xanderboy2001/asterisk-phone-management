"""Optional shared-login authentication for the web UI and API.

Authentication is off by default. Set ``ASTERISK_CLI_WEB_AUTH=basic`` to
require one shared username and password, checked with HTTP Basic auth.
Browsers show their built-in login prompt and remember the login for the
session, so NiceGUI pages and their websocket work without extra code.
"""

import base64
import binascii
import os
import secrets
from dataclasses import dataclass
from typing import Literal

from fastapi import FastAPI
from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.status import WS_1008_POLICY_VIOLATION
from starlette.types import ASGIApp, Receive, Scope, Send

from asterisk_phone_management.core.constants import log
from asterisk_phone_management.core.exceptions import AsteriskCliError

AuthMode = Literal["none", "basic"]

AUTH_MODE_ENV: str = "ASTERISK_CLI_WEB_AUTH"
AUTH_USER_ENV: str = "ASTERISK_CLI_WEB_USER"
AUTH_PASSWORD_ENV: str = "ASTERISK_CLI_WEB_PASSWORD"
_REALM: str = "Asterisk Phone Management"


@dataclass(frozen=True)
class BasicCredentials:
    """The shared login accepted by the web UI and API.

    Attributes:
        username: The required username.
        password: The required password.
    """

    username: str
    password: str


def parse_auth_mode(raw: str | None) -> AuthMode:
    """Interpret the authentication mode settings.

    Args:
        raw: The setting value. ``None`` or empty means ``none``.

    Returns:
        ``"none"`` or ``"basic"``.

    Raises:
        AsteriskCliError: If the value is not a supported mode.
    """
    mode: str = (raw or "none").strip().lower()
    if mode == "none":
        return "none"
    if mode == "basic":
        return "basic"
    msg = f"{AUTH_MODE_ENV} must be 'none' or 'basic', not {raw!r}."
    raise AsteriskCliError(msg)


def load_credentials(
    username: str | None, password: str | None
) -> BasicCredentials:
    """Build the shared login, failing if either part is missing.

    Args:
        username: The configured username.
        password: The configured password.

    Returns:
        The validated credentials.

    Raises:
        AsteriskCliError: If the username or password is empty.
    """
    missing: list[str] = []
    if username is None or not username.strip():
        missing.append(AUTH_USER_ENV)
    if password is None or not password:
        missing.append(AUTH_PASSWORD_ENV)
    if missing or username is None or password is None:
        msg = (
            f"{AUTH_MODE_ENV}=basic requires {' and '.join(missing)} "
            "to be set."
        )
        raise AsteriskCliError(msg)
    return BasicCredentials(username=username.strip(), password=password)


def check_authorization(
    header: str | None, expected: BasicCredentials
) -> bool:
    """Check an ``Authorization`` header against the shared login.

    Args:
        header: The raw header value, if the client sent one.
        expected: The credentials to accept.

    Returns:
        True if the header holds the expected username and password.
    """
    if header is None:
        return False
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "basic" or not token:
        return False
    try:
        decoded = base64.b64decode(token, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    username, separator, password = decoded.partition(":")
    if not separator:
        return False
    # Compare both parts in constant time so timing doesn't leak which
    # part is wrong.
    user_ok = secrets.compare_digest(
        username.encode(), expected.username.encode()
    )
    password_ok = secrets.compare_digest(
        password.encode(), expected.password.encode()
    )
    return user_ok and password_ok


class BasicAuthMiddleware:
    """ASGI middleware that requires the shared login on every request."""

    def __init__(self, app: ASGIApp, credentials: BasicCredentials) -> None:
        """Wrap an ASGI app.

        Args:
            app: The ASGI application to protect.
            credentials: The login every client must provide.
        """
        self.app = app
        self.credentials = credentials

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Pass authenticated requests through and challenge the rest.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive channel.
            send: The ASGI send channel.
        """
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        header = Headers(scope=scope).get("authorization")
        if check_authorization(header, self.credentials):
            await self.app(scope, receive, send)
            return

        if header is not None:
            client = scope.get("client")
            log.warning(
                "Failed login from %s", str(client[0]) if client else None
            )
        if scope["type"] == "websocket":
            await send(
                {"type": "websocket.close", "code": WS_1008_POLICY_VIOLATION}
            )
            return
        response = PlainTextResponse(
            "Authentication required",
            status_code=401,
            headers={
                "WWW-Authenticate": f'Basic realm="{_REALM}", charset="UTF-8"'
            },
        )
        await response(scope, receive, send)


def configure_auth(
    app: FastAPI,
    mode: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> AuthMode:
    """Enable the configured authentication mode on an app.

    Each argument defaults to its environment variable when not given.

    Args:
        app: The FastAPI application to protect.
        mode: ``"none"`` or ``"basic"`` (``ASTERISK_CLI_WEB_AUTH``).
        username: The shared username (``ASTERISK_CLI_WEB_USER``).
        password: The shared password (``ASTERISK_CLI_WEB_PASSWORD``).

    Returns:
        The mode that was applied.
    """
    resolved = parse_auth_mode(
        mode if mode is not None else os.environ.get(AUTH_MODE_ENV)
    )
    if resolved == "none":
        log.warning("Web authentication is disabled (%s=none).", AUTH_MODE_ENV)
        return resolved
    credentials = load_credentials(
        username if username is not None else os.environ.get(AUTH_USER_ENV),
        password
        if password is not None
        else os.environ.get(AUTH_PASSWORD_ENV),
    )
    app.add_middleware(BasicAuthMiddleware, credentials=credentials)
    log.info("Web authentication enabled (shared login).")
    return resolved
