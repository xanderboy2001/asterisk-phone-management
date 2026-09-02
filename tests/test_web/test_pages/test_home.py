"""Tests for the home page."""

from nicegui.testing import User

from asterisk_phone_management.web.pages import home

home.register_page()


async def test_home_page_shows_heading_and_cards(user: User) -> None:
    """The home page renders the heading and every configured nav card."""
    await user.open("/")
    await user.should_see("Asterisk Phone Management")
    await user.should_see("Search for a Phone")
    await user.should_see("Reset Voicemail Password")
    await user.should_see("Reboot Phone")


async def test_home_page_first_card_navigates_to_search(user: User) -> None:
    """Clicking the first card's Open button navigates to /search."""
    await user.open("/")
    user.find("Open").click()
    await user.should_see("Search by Extension")
