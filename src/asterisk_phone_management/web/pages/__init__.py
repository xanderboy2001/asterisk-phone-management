"""Pages package for Asterisk Phone Management web interface."""

from asterisk_phone_management.web.pages import (
    edit_caller_id,
    home,
    reboot_phone,
    search,
    voicemail_reset,
)

__all__: list[str] = [
    "edit_caller_id",
    "home",
    "reboot_phone",
    "search",
    "voicemail_reset",
]
