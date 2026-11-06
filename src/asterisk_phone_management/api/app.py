"""Explicit FastAPI application factory; importing does not mount the UI."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from asterisk_phone_management import __version__
from asterisk_phone_management.api.auth import configure_auth
from asterisk_phone_management.api.network_access import (
    configure_network_access,
)
from asterisk_phone_management.api.routes.search import router as search_router
from asterisk_phone_management.core.logging import configure_logging
from asterisk_phone_management.web import mount_ui


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Configure logging when the server starts, not when imported.

    Args:
        _app: The application being started.

    Yields:
        Control to the running server.
    """
    configure_logging()
    yield


def create_app() -> FastAPI:
    """Build the application and explicitly mount its UI.

    Returns:
        The configured FastAPI application.
    """
    app = FastAPI(
        title="Asterisk Management API",
        description="An API to manage and search the Asterisk Phone system.",
        version=__version__,
        lifespan=_lifespan,
    )
    app.include_router(search_router, prefix="/api/v1/search", tags=["search"])
    # Validate security configuration before mounting NiceGUI. Middleware
    # added last runs first, so the network check precedes authentication.
    configure_auth(app)
    configure_network_access(app)
    mount_ui(app)
    return app
