"""Pages package for Asterisk Phone Management web interface."""

from asterisk_phone_management.web.pages import (
    home,
    reboot_phone,
    search,
    voicemail_reset,
)

__all__: list[str] = ["home", "reboot_phone", "search", "voicemail_reset"]
