"""FastAPI application instance for configuration and router registrations.

This module initializes the primary FastAPI application and attaches API
routers for endpoints across the Asterisk management system.
"""

from fastapi import FastAPI

from asterisk_phone_management.api.routes.search import router as search_router

app = FastAPI(
    title="Asterisk Management API",
    description="An API to manage and search the Asterisk Phone system.",
    version="0.0.1",
)

app.include_router(search_router, prefix="/api/v1/search", tags=["search"])
