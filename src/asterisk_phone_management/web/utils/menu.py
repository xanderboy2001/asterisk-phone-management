"""Navigation menu component for the web interface."""

from nicegui import ui

from asterisk_phone_management.web.utils.styles import LINK_CLASSES

_NAV_LINKS: tuple[tuple[str, str], ...] = (
    ("Home", "/"),
    ("Search", "/search"),
    ("VM Reset", "/voicemail-reset"),
    ("Reboot", "/reboot-phone"),
    ("Edit Caller ID", "/edit-caller-id"),
)


def menu() -> None:
    """Renders the primary navigation links."""
    for label, target in _NAV_LINKS:
        ui.link(label, target).classes(LINK_CLASSES)
