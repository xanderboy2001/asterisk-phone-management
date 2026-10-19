"""Tests for the edit caller ID page."""

from nicegui import ui
from nicegui.testing import User

from asterisk_phone_management.web.pages import edit_caller_id

edit_caller_id.register_page()


async def test_edit_caller_id_page_shows_heading(user: User) -> None:
    """The page renders its heading and extension input."""
    await user.open("/edit-caller-id")
    await user.should_see("Edit Caller ID")
    await user.should_see("Enter an Extension")


async def test_edit_caller_id_search_without_extension_warns(
    user: User,
) -> None:
    """Searching with only whitespace shows a warning instead of searching."""
    await user.open("/edit-caller-id")
    user.find("Enter an Extension").type("   ")
    user.find(ui.button).click()
    await user.should_see("Please enter an extension.")
