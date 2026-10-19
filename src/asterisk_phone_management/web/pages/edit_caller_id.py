"""Edit caller ID page component."""

from nicegui import ui

from asterisk_phone_management.core.constants import CALLERID_DIRECTIVE
from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    FileTransactionError,
)
from asterisk_phone_management.core.theme import DRACULA
from asterisk_phone_management.core.validators import (
    validate_caller_id,
    validate_extension,
)
from asterisk_phone_management.schemas.models import ConfigMatch
from asterisk_phone_management.services.caller_id import edit_caller_id
from asterisk_phone_management.services.search import search_for_extension
from asterisk_phone_management.web.utils import theme
from asterisk_phone_management.web.utils.inputs import (
    caller_id_input,
    extension_input,
)
from asterisk_phone_management.web.utils.styles import (
    BUTTON_CLASSES,
    BUTTON_PROPS,
    BUTTON_PROPS_NEGATIVE,
    BUTTON_PROPS_POSITIVE,
    ERROR_TEXT_CLASSES,
    HEADING_CLASSES,
    RESULT_CARD_CLASSES,
    RESULTS_CONTAINER_CLASSES,
)


async def on_submit(
    extension: str | None,
    new_caller_id: str | None,
    selected_matches: list[ConfigMatch],
) -> None:
    """Handle submission of caller ID edit request.

    Args:
        extension: The target extension.
        new_caller_id: The new caller ID value.
        selected_matches: The ConfigMatch entries selected for update.
    """
    extension = (extension or "").strip()
    new_caller_id = (new_caller_id or "").strip()
    if not extension:
        ui.notify("No extension!", type="negative", textColor="dark")
        return

    if not new_caller_id:
        ui.notify("No caller ID!", type="negative", textColor="dark")
        return

    for validation_result in (
        validate_extension(extension),
        validate_caller_id(new_caller_id),
    ):
        if validation_result is not True:
            ui.notify(
                str(validation_result), type="negative", textColor="dark"
            )
            return

    if not selected_matches:
        ui.notify("No entries selected!", type="warning", textColor="dark")
        return

    count = len(selected_matches)
    plural = "s" if count != 1 else ""

    with ui.dialog() as dialog, ui.card():
        ui.label(
            f"Are you sure you want to set the caller ID of {count} "
            f"entry{plural} for extension {extension} "
            f"to '{new_caller_id}'?"
        )
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
            edit_caller_id(selected_matches, new_caller_id)
            ui.notify(
                f"Successfully set caller ID of {count} entry{plural} "
                f"for extension {extension} to '{new_caller_id}'.",
                type="positive",
                textColor="dark",
            )
        except (AsteriskCliError, FileTransactionError) as e:
            ui.notify(
                f"Failed to set caller ID for extension {extension} "
                f"to '{new_caller_id}': {e!s}",
                type="negative",
                multi_line=True,
                textColor="dark",
            )


def register_page() -> None:
    """Register the edit caller ID page route with NiceGUI."""
    current_matches: list[ConfigMatch] = []
    selected_flags: list[bool] = []

    @ui.refreshable
    def results_view() -> None:
        """Render the current matches as selectable cards."""
        if not current_matches:
            ui.label("No matches found.").classes(ERROR_TEXT_CLASSES)
            return

        for idx, match in enumerate(current_matches):

            def _toggle(checked: bool, i: int = idx) -> None:  # ruff: ignore[boolean-type-hint-positional-argument]
                selected_flags[i] = checked

            with (
                ui.card().classes(RESULT_CARD_CLASSES),
                ui.row().classes("items-center gap-2 w-full"),
            ):
                ui.checkbox(
                    value=True,
                    on_change=lambda e, i=idx: _toggle(bool(e.value), i),
                )
                with ui.column().classes("flex-grow"):
                    ui.label(
                        f"{match.file_path.name}:{match.line_number}"
                    ).classes(f"font-bold text-[{DRACULA.cyan}]")
                    ui.label(match.matched_text).classes(
                        f"text-sm text-[{DRACULA.foreground}]"
                        " font-mono overflow-x-auto"
                        " whitespace-nowrap block max-w-full pb1"
                    )

    def _selected_matches() -> list[ConfigMatch]:
        return [
            m
            for m, s in zip(current_matches, selected_flags, strict=False)
            if s
        ]

    @ui.page("/edit-caller-id")
    def edit_caller_id_page() -> None:
        """Render the edit caller ID page."""
        nonlocal current_matches, selected_flags

        def _show_update_area() -> None:
            update_area.clear()
            if not current_matches:
                return
            with update_area:  # ruff: ignore[multiple-with-statements]
                with ui.row().classes(
                    "w-full items-center justify-center gap-2 mt-4"
                ):
                    cid_input = caller_id_input()
                    ui.button(
                        text="Update Selected",
                        on_click=lambda: on_submit(
                            ext_input.value,
                            cid_input.value,
                            _selected_matches(),
                        ),
                    ).props(BUTTON_PROPS).classes(BUTTON_CLASSES)
                    cid_input.on(
                        "keydown.enter",
                        lambda: on_submit(
                            ext_input.value,
                            cid_input.value,
                            _selected_matches(),
                        ),
                    )

        def _search(ext: str | None) -> None:
            nonlocal current_matches, selected_flags

            ext = (ext or "").strip()
            if not ext:
                ui.notify(
                    "Please enter an extension.",
                    type="warning",
                    textColor="dark",
                )
                return

            extension_matches: list[ConfigMatch] = search_for_extension(ext)
            current_matches[:] = [
                match
                for match in extension_matches
                if match.matched_text.startswith(CALLERID_DIRECTIVE)
            ]
            selected_flags[:] = [True] * len(current_matches)
            results_view.refresh()
            _show_update_area()

        with theme.frame("Edit Caller ID"):
            ui.label("Edit Caller ID").classes(HEADING_CLASSES)

            with ui.row().classes(
                "w-full max-w-2xl mx-auto items-center justify-center gap-2"
            ):
                ext_input = extension_input()
                ext_input.on("keydown.enter", lambda: _search(ext_input.value))
                ui.button(
                    text="Search", on_click=lambda: _search(ext_input.value)
                ).props(BUTTON_PROPS).classes(BUTTON_CLASSES)

            with ui.column().classes(RESULTS_CONTAINER_CLASSES):
                results_view()

            update_area = ui.column().classes(
                "w-full max-w-2xl mx-auto items-center justify-center"
            )
            _show_update_area()
