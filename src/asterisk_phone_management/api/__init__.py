"""API package: FastAPI application and route definitions."""

from asterisk_phone_management.api.app import create_app
from asterisk_phone_management.api.responses import ConfigMatchResponse

__all__: list[str] = ["ConfigMatchResponse", "create_app"]
