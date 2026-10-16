"""Toggle Call Forwarding Page."""

from typing import Literal

from nicegui import ui

from asterisk_phone_management.core.constants import (
    CALL_FORWARDING_USERS,
    CallForwardingDefinition,
)
from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    FileTransactionError,
)
from asterisk_phone_management.services.call_forwarding import (
    forwarding_enabled,
    toggle_call_forwarding,
)
from asterisk_phone_management.web.utils import theme
from asterisk_phone_management.web.utils.styles import (
    BUTTON_CLASSES,
    BUTTON_PROPS,
    BUTTON_PROPS_NEGATIVE,
    BUTTON_PROPS_POSITIVE,
    HEADING_CLASSES,
)


def notify_completion(
    user: CallForwardingDefinition,
    action: Literal["enable", "disable"],
) -> None:
    """Notify the user on completion of call forwarding toggle.

    Args:
        user: User whose call forwarding was toggled.
        action: Action that occurred.
    """
    notify_string = f"{action.capitalize()}d call forwarding for {user.name}."
    ui.notify(
        message=notify_string,
        type="positive",
        textColor="dark",
    )


async def on_submit(user: CallForwardingDefinition) -> None:
    """Execute call forwarding toggle for specified user.

    Args:
        user: User whose call forwarding should be toggled.
    """
    if not user:
        ui.notify("No user selected!", type="warning", textColor="dark")
        return

    with ui.dialog() as dialog, ui.card():
        message: str = (
            "Call forwarding is enabled. Would you like to disable it?"
            if forwarding_enabled(user)
            else "Call forwarding is disabled. Would you like to enable it?"
        )
        ui.label(message)
        with ui.row().classes("w-full justify-end"):
            ui.button(
                "No", on_click=lambda: dialog.submit(result=False)
            ).classes(BUTTON_CLASSES).props(BUTTON_PROPS_NEGATIVE).mark(
                "confirm-no"
            )
            ui.button(
                "Yes", on_click=lambda: dialog.submit(result=True)
            ).classes(BUTTON_CLASSES).props(BUTTON_PROPS_POSITIVE).mark(
                "confirm-yes"
            )

    confirmed = await dialog

    if confirmed:
        if forwarding_enabled(user):
            action: str = "disable"
        else:
            action = "enable"
        try:
            toggle_call_forwarding(user, action=action)
            notify_completion(user, action)
        except (AsteriskCliError, FileTransactionError) as e:
            ui.notify(
                f"Failed to toggle call forwarding for {user.name}: {e!s}",
                type="negative",
                multi_line=True,
                textColor="dark",
            )
    else:
        ui.notify("Cancelled", type="info", textColor="dark")


def register_page() -> None:
    """Register the toggle call forwarding page route with NiceGUI."""

    @ui.page("/toggle-call-forwarding")
    def toggle_call_forwarding_page() -> None:
        """Render the toggle call forwarding page."""
        with theme.frame("Toggle Call Forwarding"):
            ui.label("Toggle Call Forwarding").classes(HEADING_CLASSES)
            radio_select = ui.radio(
                {
                    user: f"{user.name} ({user.extension})"
                    for user in CALL_FORWARDING_USERS
                }
            )

            ui.button(
                text="Submit", on_click=lambda: on_submit(radio_select.value)
            ).classes(BUTTON_CLASSES).props(BUTTON_PROPS)
