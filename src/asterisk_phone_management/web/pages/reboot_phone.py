"""Phone reboot page component."""

from nicegui import ui

from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    DeviceCommunicationError,
)
from asterisk_phone_management.core.validators import validate_extension
from asterisk_phone_management.services.device_actions import reboot_phone
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
    """Handle submission of phone reboot request.

    Args:
        extension: The target phone extension to reboot.
    """
    extension = (extension or "").strip()
    if not extension:
        ui.notify("No data!", type="negative", textColor="dark")
        return

    validation_result = validate_extension(extension)
    if validation_result is not True:
        ui.notify(str(validation_result), type="negative", textColor="dark")
        return

    with ui.dialog() as dialog, ui.card():
        ui.label(f"Are you sure you want to reboot extension {extension}?")
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
        try:
            ui.notify(
                f"Attempting to reboot {extension}...",
                type="info",
                textColor="dark",
            )
            reboot_phone(extension)
            ui.notify(
                f"Successfully sent reboot command to {extension}.",
                type="positive",
            )
        except DeviceCommunicationError as e:
            ui.notify(
                f"Failed to reboot {extension}: {e!s}",
                type="negative",
                multi_line=True,
                textColor="dark",
            )
        except AsteriskCliError as e:
            ui.notify(
                f"An unexpected error occurred: {e!s}",
                type="negative",
                textColor="dark",
            )


def register_page() -> None:
    """Register the reboot phone page route with NiceGUI."""

    @ui.page("/reboot-phone")
    def reboot_phone_page() -> None:
        """Render the reboot phone page."""
        with theme.frame("Reboot Phone"):
            ui.label("Reboot a Phone").classes(HEADING_CLASSES)

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
