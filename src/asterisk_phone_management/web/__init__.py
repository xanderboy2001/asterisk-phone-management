"""Web package initialization for Asterisk Phone Management."""

from asterisk_phone_management.web.app import mount_ui

__all__: list[str] = ["mount_ui"]
