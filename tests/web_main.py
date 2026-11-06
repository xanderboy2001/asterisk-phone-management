"""Explicit startup script for NiceGUI's simulated browser tests."""

from asterisk_phone_management.api.app import create_app

app = create_app()
