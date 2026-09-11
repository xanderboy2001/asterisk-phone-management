"""Voicemail reset page component."""

from nicegui import ui

from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    FileTransactionError,
)
from asterisk_phone_management.services.voicemail import reset_vm_password
from asterisk_phone_management.web.utils import theme
from asterisk_phone_management.web.utils.inputs import extension_input
from asterisk_phone_management.web.utils.styles import (
    BUTTON_CLASSES,
    BUTTON_PROPS,
    BUTTON_PROPS_NEGATIVE,
    BUTTON_PROPS_POSITIVE,
    HEADING_CLASSES,
)


async def on_submit(extension: str | None) -> None:
    """Handle submission of voicemail password reset request.

    Args:
        extension: Target extension for resetting the voicemail password.
    """
    if not extension:
        ui.notify("No data!", type="negative")
        return

    with ui.dialog() as dialog, ui.card():
        ui.label(
            "Are you sure you want to reset the voicemail "
            f"password for {extension}?"
        )
        with ui.row().classes("w-full justify-end"):
            ui.button(
                "No", on_click=lambda: dialog.submit(result=False)
            ).classes(BUTTON_CLASSES).props(BUTTON_PROPS_NEGATIVE)
            ui.button(
                "Yes", on_click=lambda: dialog.submit(result=True)
            ).classes(BUTTON_CLASSES).props(BUTTON_PROPS_POSITIVE)

    confirmed = await dialog

    if confirmed:
        try:
            ui.notify(
                f"Resetting voicemail password for {extension}...", type="info"
            )
            reset_vm_password(extension=extension, new_pin=extension)
            ui.notify(
                f"Successfully reset voicemail password for {extension}.",
                type="positive",
            )
        except (AsteriskCliError, FileTransactionError) as e:
            ui.notify(
                f"Failed to reset voicemail password for {extension}: {e!s}",
                type="negative",
                multi_line=True,
            )


def register_page() -> None:
    """Register the voicemail reset page route with NiceGUI."""

    @ui.page("/voicemail-reset")
    def voicemail_reset_page() -> None:
        """Render the voicemail password reset page."""
        with theme.frame("Reset Voicemail Password"):
            ui.label("Reset a Voicemail Password").classes(HEADING_CLASSES)

            with ui.row().classes(
                "w-full max-w-2xl mx-auto items-center justify-center gap-2"
            ):
                input_obj = extension_input()
                input_obj.on(
                    "keydown.enter", lambda: on_submit(input_obj.value)
                )
                ui.button(
                    text="Submit", on_click=lambda: on_submit(input_obj.value)
                ).classes(BUTTON_CLASSES).props(BUTTON_PROPS)
