"""Shared handling for unexpected errors in web page handlers."""

from nicegui import ui

from asterisk_phone_management.core.constants import log


def report_unexpected_error(action: str) -> None:
    """Log the current exception and tell the user something went wrong.

    Call this from an ``except Exception`` block in a page handler, after
    the handlers for expected errors. The traceback goes to the server
    log; the user sees a short message without internal details.

    Args:
        action: What the user was trying to do, e.g. ``"reboot 1001"``.
            Used in both the log entry and the notification.
    """
    log.exception("Unexpected error while trying to %s", action)
    ui.notify(
        f"Couldn't {action}: unexpected error. Details are in the server log.",
        type="negative",
        multi_line=True,
        textColor="dark",
    )
