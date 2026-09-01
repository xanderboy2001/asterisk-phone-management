"""Phone reboot page component."""

from nicegui import ui

from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    DeviceCommunicationError,
)
from asterisk_phone_management.services.device_actions import reboot_phone
from asterisk_phone_management.web.utils import theme
from asterisk_phone_management.web.utils.inputs import extension_input
from asterisk_phone_management.web.utils.styles import (
    BUTTON_CLASSES,
    BUTTON_PROPS,
    HEADING_CLASSES,
)


async def on_submit(extension: str | None) -> None:
    """Handle submission of phone reboot request.

    Args:
        extension: The target phone extension to reboot.
    """
    if not extension:
        ui.notify("No data!", type="negative")
        return

    with ui.dialog() as dialog, ui.card():
        ui.label(f"Are you sure you want to reboot extension {extension}?")
        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=lambda: dialog.submit(result=False))
            ui.button(
                "Reboot", on_click=lambda: dialog.submit(result=True)
            ).props("color=negative")

    confirmed = await dialog

    if confirmed:
        try:
            ui.notify(f"Attempting to reboot {extension}...", type="info")
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
            )
        except AsteriskCliError as e:
            ui.notify(f"An unexpected error occurred: {e!s}", type="negative")


def register_page() -> None:
    """Register the reboot phone page route with NiceGUI."""

    @ui.page("/reboot-phone")
    def reboot_phone_page() -> None:
        with theme.frame("Reboot Phone"):
            ui.label("Reboot a Phone").classes(HEADING_CLASSES)

            with ui.row().classes(
                "w-full max-w-2x1 mx-auto items-center justify-center gap-2"
            ):
                input_obj = extension_input()
                input_obj.on(
                    "keydown.enter", lambda: on_submit(input_obj.value)
                )
                ui.button(
                    text="Submit", on_click=lambda: on_submit(input_obj.value)
                ).classes(BUTTON_CLASSES).props(BUTTON_PROPS)
