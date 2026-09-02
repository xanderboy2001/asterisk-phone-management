"""Tests for the shared Dracula-themed page frame."""

from nicegui import ui
from nicegui.testing import User

from asterisk_phone_management.web.utils import theme


async def test_frame_renders_header_title_and_body(user: User) -> None:
    """The frame renders the app title, given nav title, menu, and body."""

    @ui.page("/__test_theme")
    def _theme_test_page() -> None:
        """Scratch page rendering the shared frame for isolated testing."""
        with theme.frame("Test Section"):
            ui.label("Body content")

    await user.open("/__test_theme")
    await user.should_see("Asterisk Phone Management")
    await user.should_see("Test Section")
    await user.should_see("Body content")
    await user.should_see("Home")
    await user.should_see("Search")
