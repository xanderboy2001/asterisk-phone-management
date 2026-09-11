"""App module for web interface."""

from fastapi import FastAPI
from nicegui import ui

from asterisk_phone_management.web.pages import (
    edit_caller_id,
    home,
    reboot_phone,
    search,
    toggle_call_forwarding,
    voicemail_reset,
)


def mount_ui(app: FastAPI) -> None:
    """Mounts the NiceGUI user interface onto the FastAPI application.

    Args:
        app: The FastAPI application instance to attach NiceGUI to.
    """
    home.register_page()
    search.register_page()
    reboot_phone.register_page()
    voicemail_reset.register_page()
    edit_caller_id.register_page()
    toggle_call_forwarding.register_page()
    ui.run_with(app=app, title="Asterisk Phone Management", favicon="🔧")
