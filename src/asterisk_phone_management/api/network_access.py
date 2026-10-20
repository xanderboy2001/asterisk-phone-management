"""Restrict the web UI and API to trusted client networks.

Requests from addresses outside the configured networks are rejected
before they reach any page, API route, or websocket. This applies whether
or not user authentication is enabled.
"""

import ipaddress
import os

from fastapi import FastAPI
from starlette.responses import PlainTextResponse
from starlette.status import WS_1008_POLICY_VIOLATION
from starlette.types import ASGIApp, Receive, Scope, Send

from asterisk_phone_management.core.constants import log
from asterisk_phone_management.core.exceptions import AsteriskCliError

Network = ipaddress.IPv4Network | ipaddress.IPv6Network

ALLOWED_NETWORKS_ENV: str = "ASTERISK_CLI_ALLOWED_NETWORKS"


def parse_networks(raw: str) -> tuple[Network, ...]:
    """Parse a comma-separated list of IP networks.

    Args:
        raw: Networks in CIDR form, e.g. ``"10.20.0.0/24, 127.0.0.1"``.
            A bare address is treated as a single-host network.

    Returns:
        The parsed networks. Empty if ``raw`` contains no entries.

    Raises:
        AsteriskCliError: If any entry is not a valid address or network.
    """
    networks: list[Network] = []
    for item in raw.split(","):
        entry = item.strip()
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError as e:
            msg = f"Invalid network in {ALLOWED_NETWORKS_ENV}: {entry!r}"
            raise AsteriskCliError(msg) from e
    return tuple(networks)


def is_allowed(host: str | None, networks: tuple[Network, ...]) -> bool:
    """Check whether a client address falls inside an allowed network.

    Args:
        host: The client address from the ASGI scope, if known.
        networks: The allowed networks.

    Returns:
        True if the address is inside any allowed network.
    """
    if host is None:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    # Dual-stack sockets report IPv4 clients as ::ffff:a.b.c.d
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return any(address in network for network in networks)


class ClientNetworkMiddleware:
    """ASGI middleware that rejects clients outside the allowed networks."""

    def __init__(self, app: ASGIApp, networks: tuple[Network, ...]) -> None:
        """Wrap an ASGI app.

        Args:
            app: The ASGI application to protect.
            networks: Networks whose clients may use the app.
        """
        self.app = app
        self.networks = networks

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Pass allowed requests through and reject everything else.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive channel.
            send: The ASGI send channel.
        """
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        host = str(client[0]) if client else None
        if is_allowed(host, self.networks):
            await self.app(scope, receive, send)
            return

        log.warning("Rejected %s connection from %s", scope["type"], host)
        if scope["type"] == "websocket":
            await send(
                {"type": "websocket.close", "code": WS_1008_POLICY_VIOLATION}
            )
            return
        response = PlainTextResponse("Forbidden", status_code=403)
        await response(scope, receive, send)


def configure_network_access(app: FastAPI, raw: str | None = None) -> None:
    """Install the network allowlist on an app, if one is configured.

    Args:
        app: The FastAPI application to protect.
        raw: The allowlist string. Defaults to the
            ``ASTERISK_CLI_ALLOWED_NETWORKS`` environment variable.
    """
    if raw is None:
        raw = os.environ.get(ALLOWED_NETWORKS_ENV, "")
    networks = parse_networks(raw)
    if not networks:
        log.warning(
            "%s is not set: the web UI and API cannot accept connections from "
            "any address that can reach this server.",
            ALLOWED_NETWORKS_ENV,
        )
        return
    app.add_middleware(ClientNetworkMiddleware, networks=networks)
    log.info(
        "Web UI and API restricted to %s",
        ", ".join(str(network) for network in networks),
    )
