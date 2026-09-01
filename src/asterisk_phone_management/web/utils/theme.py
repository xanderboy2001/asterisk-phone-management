"""Theme layout utilities implementing the Dracula color specification."""

from collections.abc import Generator
from contextlib import contextmanager

from nicegui import ui

from asterisk_phone_management.core.theme import DRACULA
from asterisk_phone_management.web.utils.menu import menu


@contextmanager
def frame(navigation_title: str) -> Generator[None]:
    """Context manager for rendering a page frame styled with Dracula theme.

    Args:
        navigation_title: Title text to display in the header bar.

    Yields:
        None: Yields control back to the page context block.
    """
    ui.dark_mode().enable()
    ui.colors(
        primary=DRACULA.purple,
        secondary=DRACULA.comment,
        accent=DRACULA.pink,
        dark=DRACULA.background,
        positive=DRACULA.green,
        negative=DRACULA.red,
        info=DRACULA.cyan,
        warning=DRACULA.orange,
    )

    # Set background and base text colors globally
    ui.query("body").style(
        f"background-color: {DRACULA.background}; color: {DRACULA.foreground};"
    )

    with ui.header().classes(
        f"bg-[{DRACULA.current_line}] text-[{DRACULA.foreground}]"
        " items-center px-4 py-2"
    ):
        ui.label("Asterisk Phone Management").classes(
            f"font-bold text-lg text-[{DRACULA.cyan}]"
        )
        ui.space()
        ui.label(navigation_title).classes(
            f"text-[{DRACULA.pink}] font-medium"
        )
        ui.space()
        with ui.row().classes("gap-4"):
            menu()

    with ui.column().classes(
        "absolute-center items-center w-full max-w-4xl px-4"
    ):
        yield
