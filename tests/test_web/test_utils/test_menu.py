"""Tests for the navigation menu component."""

from nicegui import ui
from nicegui.testing import User

from asterisk_phone_management.web.pages import home
from asterisk_phone_management.web.utils.menu import menu


async def test_menu_renders_all_navigation_links(user: User) -> None:
    """Every configured navigation link is rendered with its label."""

    @ui.page("/__test_menu")
    def _menu_test_page() -> None:
        """Scratch page rendering the nav menu in isolation."""
        menu()

    await user.open("/__test_menu")
    for label in (
        "Call Forwarding",
        "Edit Caller ID",
        "Home",
        "Reboot",
        "Search",
        "VM Reset",
    ):
        await user.should_see(label)


async def test_menu_links_to_every_page(user: User) -> None:
    """The nav menu links to every page that has a home page card."""

    @ui.page("/__test_menu_links")
    def _menu_links_test_page() -> None:
        """Scratch page rendering the nav menu in isolation."""
        menu()

    await user.open("/__test_menu_links")
    hrefs = {link.props["href"] for link in user.find(ui.link).elements}

    assert {card.target for card in home._CARDS} <= hrefs
