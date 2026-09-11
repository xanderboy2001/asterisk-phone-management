"""Search page component for Asterisk Phone Management."""

from nicegui import ui
from nicegui.elements.input import Input
from nicegui.elements.radio import Radio

from asterisk_phone_management.core.constants import (
    SEARCH_BY_CALLER_ID,
    SEARCH_BY_EXTENSION,
    SEARCH_BY_MAC,
    SearchMethod,
)
from asterisk_phone_management.core.theme import DRACULA
from asterisk_phone_management.schemas.models import ConfigMatch
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

"""Mapping of search method identifiers to display labels."""
_SEARCH_METHODS: dict[str, str] = {
    SEARCH_BY_EXTENSION: "Search by Extension",
    SEARCH_BY_MAC: "Search by MAC Address",
    SEARCH_BY_CALLER_ID: "Search by Caller ID",
}

"""Union type for search results returned by the search functions."""
_SearchResult = ConfigMatch | list[ConfigMatch]


def register_page() -> None:
    """Register the search page route with NiceGUI."""

    @ui.page("/search")
    def search_page() -> None:
        """Render the search page view for looking up phone configurations."""
        with theme.frame("Search"):
            ui.label("Search for a Phone").classes(HEADING_CLASSES)

            search_method: Radio = ui.radio(
                options=_SEARCH_METHODS, value=SEARCH_BY_EXTENSION
            ).classes(f"flex justify-center mb-4 text-[{DRACULA.foreground}]")

            results_container = ui.column().classes(RESULTS_CONTAINER_CLASSES)

            def on_search(
                search_val: str | None, _method: SearchMethod
            ) -> None:
                """Execute search query based on selected method.

                Args:
                    search_val: Search query string entered by the user.
                    _method: Search method ("ext", "mac", or "callerid").
                """
                results_container.clear()

                if not search_val:
                    ui.notify(
                        message="Please enter a search value.",
                        type="warning",
                        textColor="dark",
                    )
                    return

                response_data: _SearchResult | None = None
                if _method == SEARCH_BY_EXTENSION:
                    response_data = search_for_extension(extension=search_val)
                elif _method == SEARCH_BY_MAC:
                    response_data = search_for_mac_address(
                        mac_address=search_val
                    )
                elif _method == SEARCH_BY_CALLER_ID:
                    response_data = search_for_caller_id(caller_id=search_val)

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
                method: SearchMethod,
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
                    if search_method.value == SEARCH_BY_EXTENSION:
                        _search_field(extension_input(), SEARCH_BY_EXTENSION)

                    elif search_method.value == SEARCH_BY_MAC:
                        _search_field(mac_address_input(), SEARCH_BY_MAC)

                    elif search_method.value == SEARCH_BY_CALLER_ID:
                        _search_field(caller_id_input(), SEARCH_BY_CALLER_ID)

            search_method.on_value_change(search_form.refresh)
            search_form()
