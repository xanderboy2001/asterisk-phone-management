"""Tests for the edit caller ID page."""

import importlib
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest
from nicegui import ui
from nicegui.testing import User

from asterisk_phone_management.core.exceptions import AsteriskCliError
from asterisk_phone_management.schemas.models import ConfigMatch
from asterisk_phone_management.web.pages import edit_caller_id

edit_caller_id.register_page()

SIP_CONF = Path("sip.conf")
MATCHES: dict[str, list[ConfigMatch]] = {
    "1001": [
        ConfigMatch(
            file_path=SIP_CONF,
            line_number=6,
            matched_text='callerid="John Doe" <1001>',
        ),
        ConfigMatch(
            file_path=SIP_CONF,
            line_number=14,
            matched_text='callerid="John Desk" <1001>',
        ),
    ],
}


def _page_modules() -> set[ModuleType]:
    """Return every copy of the page module that may serve the route.

    NiceGUI's test harness re-imports page modules before tests, so the
    copy imported at the top of this file and the copy the app loaded can
    differ. Patching both guarantees the page sees the fake services.

    Returns:
        The page module objects to patch.
    """
    return {edit_caller_id, importlib.import_module(edit_caller_id.__name__)}


@pytest.fixture
def fake_search(user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve search results from ``MATCHES`` instead of real files."""
    del user  # Only needed so the app (and page module) is leaded first.
    for module in _page_modules():
        monkeypatch.setattr(
            module,
            "search_for_extension",
            lambda extension: MATCHES.get(extension, []),
        )


@pytest.fixture
def mock_edit(user: User, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace the caller ID service so no files are written.

    Returns:
        The mock that stands in for ``edit_caller_id``.
    """
    del user  # Only needed so the app (and page module) is leaded first.
    mock = MagicMock()
    for module in _page_modules():
        monkeypatch.setattr(module, "edit_caller_id", mock)
    return mock


async def _search(user: User, extension: str) -> None:
    """Open the page and search for an extension.

    Args:
        user: The simulated browser session.
        extension: The extension to search for.
    """
    await user.open("/edit-caller-id")
    user.find("Enter an Extension").type(extension)
    user.find(marker="search-button").click()


async def _update(user: User, caller_id: str) -> None:
    """Enter a caller ID, submit, confirm, and wait for the result.

    Args:
        user: The simulated browser session.
        caller_id: The new caller ID to enter.
    """
    user.find("Enter a Caller ID").type(caller_id)
    user.find("Update Selected").click()
    await user.should_see(marker="confirm-yes")
    user.find(marker="confirm-yes").click()
    await user.should_see("Successfully set caller ID")


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


@pytest.mark.usefixtures("fake_search")
async def test_search_shows_matches_and_update_area(user: User) -> None:
    """A search lists each caller ID line and shows update controls."""
    await _search(user, "1001")
    await user.should_see("sip.conf:6")
    await user.should_see("sip.conf:14")
    await user.should_see("Update Selected")


@pytest.mark.usefixtures("fake_search")
async def test_search_without_matches(user: User) -> None:
    await _search(user, "9999")
    await user.should_see("No matches found.")
    await user.should_not_see("Update Selected")


@pytest.mark.usefixtures("fake_search")
async def test_update_sends_all_selected_matches(
    user: User, mock_edit: MagicMock
) -> None:
    """With every box ticked, every match is updated."""
    await _search(user, "1001")
    await _update(user, '"New Name" <1001>')
    await user.should_see("Successfully set caller ID of 2 entries")
    mock_edit.assert_called_once_with(MATCHES["1001"], '"New Name" <1001>')


@pytest.mark.usefixtures("fake_search")
async def test_unchecked_match_is_not_updated(
    user: User, mock_edit: MagicMock
) -> None:
    """Unticking a box removes that line from the update."""
    await _search(user, "1001")
    await user.should_see(marker="select-0")
    user.find(marker="select-0").click()
    await _update(user, '"New Name" <1001>')
    mock_edit.assert_called_once_with(
        [MATCHES["1001"][1]], '"New Name" <1001>'
    )


@pytest.mark.usefixtures("fake_search")
async def test_unchecking_everything_blocks_update(
    user: User, mock_edit: MagicMock
) -> None:
    """With nothing ticked, the update is refused."""
    await _search(user, "1001")
    await user.should_see(marker="select-0")
    user.find(marker="select-0").click()
    user.find(marker="select-1").click()
    user.find("Enter a Caller ID").type('"New Name" <1001>')
    user.find("Update Selected").click()
    await user.should_see("No entries selected!")
    mock_edit.assert_not_called()


@pytest.mark.usefixtures("fake_search")
async def test_new_search_resets_selection(
    user: User, mock_edit: MagicMock
) -> None:
    """Searching again re-ticks every result."""
    await _search(user, "1001")
    await user.should_see(marker="select-0")
    user.find(marker="select-0").click()
    user.find(marker="search-button").click()
    await _update(user, '"New Name" <1001>')
    mock_edit.assert_called_once_with(MATCHES["1001"], '"New Name" <1001>')


@pytest.mark.usefixtures("fake_search")
async def test_update_uses_searched_extension(
    user: User, mock_edit: MagicMock
) -> None:
    """Changing the extension box after searching doesn't redirect the edit."""
    await _search(user, "1001")
    user.find("Enter an Extension").clear().type("2002")
    await _update(user, '"New Name" <1001>')
    await user.should_see("for extension 1001")
    mock_edit.assert_called_once_with(MATCHES["1001"], '"New Name" <1001>')


@pytest.mark.usefixtures("fake_search")
async def test_users_do_not_share_results(
    create_user: Callable[[], User], mock_edit: MagicMock
) -> None:
    """One user's search never changes another user's results (F-10)."""
    alice = create_user()
    bob = create_user()

    await _search(alice, "1001")
    await alice.should_see("sip.conf:6")

    await _search(bob, "9999")
    await bob.should_see("No matches found.")
    await bob.should_not_see("sip.conf:6")

    await alice.should_see("sip.conf:6")
    await _update(alice, '"New Name" <1001>')
    mock_edit.assert_called_once_with(MATCHES["1001"], '"New Name" <1001>')


@pytest.mark.usefixtures("fake_search", "expect_error_log")
async def test_unexpected_error_is_reported(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unexpected error while saving shows a generic message."""
    for module in _page_modules():
        monkeypatch.setattr(
            module,
            "edit_caller_id",
            MagicMock(side_effect=RuntimeError("bug")),
        )
    await _search(user, "1001")
    user.find("Enter a Caller ID").type('"New Name" <1001>')
    user.find("Update Selected").click()
    await user.should_see(marker="confirm-yes")
    user.find(marker="confirm-yes").click()
    await user.should_see(
        "Couldn't set the caller ID for extension 1001: unexpected error"
    )


@pytest.mark.usefixtures("fake_search", "mock_edit")
async def test_update_reloads_sip(user: User, mock_reload: MagicMock) -> None:
    """A successful caller ID change reloads SIP (F-17)."""
    await _search(user, "1001")
    await _update(user, '"New Name" <1001>')
    await user.should_see("Asterisk reloaded the SIP configuration.")
    mock_reload.assert_called_once_with(
        command="sip reload", friendly_name="SIP configuration"
    )


@pytest.mark.usefixtures("fake_search")
async def test_failed_update_does_not_reload(
    user: User, monkeypatch: pytest.MonkeyPatch, mock_reload: MagicMock
) -> None:
    """A failed caller ID change doesn't reload Asterisk."""
    for module in _page_modules():
        monkeypatch.setattr(
            module,
            "edit_caller_id",
            MagicMock(side_effect=AsteriskCliError("line changed")),
        )
    await _search(user, "1001")
    user.find("Enter a Caller ID").type('"New Name" <1001>')
    user.find("Update Selected").click()
    await user.should_see(marker="confirm-yes")
    user.find(marker="confirm-yes").click()
    await user.should_see("Failed to set caller ID")
    mock_reload.assert_not_called()
