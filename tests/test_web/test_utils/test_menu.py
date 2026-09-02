"""Tests for the navigation menu component."""

from nicegui import ui
from nicegui.testing import User

from asterisk_phone_management.web.utils.menu import menu


async def test_menu_renders_all_navigation_links(user: User) -> None:
    """Every configured navigation link is rendered with its label."""

    @ui.page("/__test_menu")
    def _menu_test_page() -> None:
        """Scratch page rendering the nav menu in isolation."""
        menu()

    await user.open("/__test_menu")
    for label in ("Home", "Search", "VM Reset", "Reboot"):
        await user.should_see(label)
