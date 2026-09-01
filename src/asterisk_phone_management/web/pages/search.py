"""Search page component for Asterisk Phone Management."""

from typing import Any, Literal

from nicegui import ui
from nicegui.elements.input import Input
from nicegui.elements.radio import Radio

from asterisk_phone_management.core.theme import DRACULA
from asterisk_phone_management.services.search import (
    search_for_caller_id,
    search_for_extension,
    search_for_mac_address,
)
from asterisk_phone_management.web.utils import theme
from asterisk_phone_management.web.utils.inputs import (
    caller_id_input,
    extension_input,
    mac_address_input,
)
from asterisk_phone_management.web.utils.styles import (
    BUTTON_CLASSES,
    BUTTON_PROPS,
    ERROR_TEXT_CLASSES,
    HEADING_CLASSES,
    RESULT_CARD_CLASSES,
    RESULTS_CONTAINER_CLASSES,
)

_SearchMethod = Literal["ext", "mac", "callerid"]

_SEARCH_METHODS: dict[_SearchMethod, str] = {
    "ext": "Search by Extension",
    "mac": "Search by MAC Address",
    "callerid": "Search by Caller ID",
}


def register_page() -> None:
    """Register the search page route with NiceGUI."""

    @ui.page("/search")
    def search_page() -> None:
        """Render the search page view for looking up phone configurations."""
        with theme.frame("Search"):
            ui.label("Search for a Phone").classes(HEADING_CLASSES)

            search_method: Radio = ui.radio(
                options=_SEARCH_METHODS, value="ext"
            ).classes(f"flex justify-center mb-4 text-[{DRACULA.foreground}]")

            results_container = ui.column().classes(RESULTS_CONTAINER_CLASSES)

            def on_search(
                search_val: str | None, _method: _SearchMethod
            ) -> None:
                """Execute search query based on selected method.

                Args:
                    search_val: Search query string entered by the user.
                    _method: Search method ("ext", "mac", or "callerid").
                """
                results_container.clear()

                if not search_val:
                    ui.notify(
                        message="Please enter a search value.", type="warning"
                    )
                    return

                response_data: list[Any] | None
                if _method == "ext":
                    response_data = search_for_extension(extension=search_val)
                elif _method == "mac":
                    response_data = search_for_mac_address(
                        mac_address=search_val
                    )
                elif _method == "callerid":
                    response_data = search_for_caller_id(caller_id=search_val)
                else:
                    ui.notify("Invalid search method.", type="warning")
                    return

                if not response_data:
                    with results_container:
                        ui.label("No matches found.").classes(
                            ERROR_TEXT_CLASSES
                        )
                    return

                with results_container:
                    for match in response_data:
                        with ui.card().classes(RESULT_CARD_CLASSES):
                            ui.label(
                                f"{match.file_path.name}:{match.line_number}"
                            ).classes(f"font-bold text-[{DRACULA.cyan}]")
                            ui.label(match.matched_text).classes(
                                f"text-sm text-[{DRACULA.foreground}]"
                                " font-mono overflow-x-auto"
                                " whitespace-nowrap block max-w-full pb1"
                            )

            def _search_field(
                field: Input,
                method: _SearchMethod,
            ) -> None:
                """Attach search events to the provided input field."""
                field.on(
                    "keydown.enter", lambda: on_search(field.value, method)
                )
                ui.button(
                    text="Search",
                    on_click=lambda: on_search(field.value, method),
                ).props(BUTTON_PROPS).classes(BUTTON_CLASSES)

            @ui.refreshable
            def search_form() -> None:
                """Render dynamic search input controls."""
                results_container.clear()
                with ui.row().classes(
                    "w-full max-w-2xl mx-auto items-center"
                    " justify-center gap-2"
                ):
                    if search_method.value == "ext":
                        _search_field(extension_input(), "ext")

                    elif search_method.value == "mac":
                        _search_field(mac_address_input(), "mac")

                    elif search_method.value == "callerid":
                        _search_field(caller_id_input(), "callerid")

            search_method.on_value_change(search_form.refresh)
            search_form()
