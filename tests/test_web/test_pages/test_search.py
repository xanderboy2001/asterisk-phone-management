"""Tests for the search page."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from nicegui import ui
from nicegui.testing import User

from asterisk_phone_management.schemas.models import ConfigMatch
from asterisk_phone_management.web.pages import search as search_page

search_page.register_page()


async def test_search_page_defaults_to_extension_search(user: User) -> None:
    """The search page defaults to the extension search input."""
    await user.open("/search")
    await user.should_see("Search for a Phone")
    await user.should_see("Enter an Extension")


async def test_search_with_empty_value_warns(user: User) -> None:
    """Searching with no value shows a warning notification."""
    await user.open("/search")
    user.find(ui.button).click()
    await user.should_see("Please enter a search value.")


async def test_search_extension_no_matches(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No matches renders the 'No matches found.' message."""
    monkeypatch.setattr(
        search_page,
        "search_for_extension",
        lambda extension=None: [],
    )
    await user.open("/search")
    user.find("Enter an Extension").type("1234")
    user.find(ui.button).click()
    await user.should_see("No matches found.")


async def test_search_extension_with_matches(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Matches are rendered with their file location and matched text."""
    matches = [
        ConfigMatch(
            file_path=Path("sip.conf"),
            line_number=5,
            matched_text="exten => 1234,1,Dial(SIP/1234)",
        )
    ]
    monkeypatch.setattr(
        search_page,
        "search_for_extension",
        lambda extension=None: matches,
    )
    await user.open("/search")
    user.find("Enter an Extension").type("1234")
    user.find(ui.button).click()
    await user.should_see("sip.conf:5")
    await user.should_see("exten => 1234,1,Dial(SIP/1234)")


async def test_search_mac_address_is_normalized(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A lowercase, colon-separated MAC is searched in normalized form."""
    mock_search = MagicMock(return_value=[])
    monkeypatch.setattr(search_page, "search_for_mac_address", mock_search)
    await user.open("/search")
    user.find("Search by MAC Address").click()
    await user.should_see("Enter a MAC Address")
    user.find("Enter a MAC Address").type("aa:bb:cc:dd:ee:ff")
    user.find(ui.button).click()
    await user.should_see("No matches found.")
    mock_search.assert_called_once_with(mac_address="AABBCCDDEEFF")


async def test_search_invalid_mac_address_is_rejected(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An invalid MAC shows the validation error and isn't searched."""
    mock_search = MagicMock(return_value=[])
    monkeypatch.setattr(search_page, "search_for_mac_address", mock_search)
    await user.open("/search")
    user.find("Search by MAC Address").click()
    await user.should_see("Enter a MAC Address")
    user.find("Enter a MAC Address").type("not-a-mac")
    user.find(ui.button).click()
    await user.should_see("MAC address must be 12 digits.")
    mock_search.assert_not_called()


async def test_search_switch_to_mac_address(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Switching methods swaps in the MAC address input and search call."""
    matches = [
        ConfigMatch(
            file_path=Path("sip.conf"),
            line_number=2,
            matched_text="; SEPAABBCCDDEEFF",
        )
    ]
    monkeypatch.setattr(
        search_page,
        "search_for_mac_address",
        lambda mac_address=None: matches,
    )
    await user.open("/search")
    user.find("Search by MAC Address").click()
    await user.should_see("Enter a MAC Address")
    user.find("Enter a MAC Address").type("AABBCCDDEEFF")
    user.find(ui.button).click()
    await user.should_see("sip.conf:2")


async def test_search_switch_to_caller_id(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Switching methods swaps in the Caller ID input and search call."""
    matches = [
        ConfigMatch(
            file_path=Path("sip.conf"),
            line_number=3,
            matched_text='callerid="John Smith" <1234>',
        )
    ]
    monkeypatch.setattr(
        search_page,
        "search_for_caller_id",
        lambda caller_id=None: matches,
    )
    await user.open("/search")
    user.find("Search by Caller ID").click()
    await user.should_see("Enter a Caller ID")
    user.find("Enter a Caller ID").type("John Smith")
    user.find(ui.button).click()
    await user.should_see("sip.conf:3")


async def test_search_keydown_triggers_search(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pressing enter on the input triggers the search action."""
    matches = [
        ConfigMatch(
            file_path=Path("sip.conf"),
            line_number=5,
            matched_text='callerid="John" <1001>',
        )
    ]
    monkeypatch.setattr(
        search_page,
        "search_for_extension",
        lambda extension=None: matches,
    )
    await user.open("/search")
    input_field = user.find("Enter an Extension")
    input_field.type("1001")
    input_field.trigger("keydown.enter")
    await user.should_see("sip.conf:5")


@pytest.mark.usefixtures("expect_error_log")
async def test_search_unexpected_error_is_reported(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing search shows a generic message instead of nothing."""
    monkeypatch.setattr(
        search_page,
        "search_for_extension",
        MagicMock(side_effect=PermissionError("sip.conf")),
    )
    await user.open("/search")
    user.find("Enter an Extension").type("1234")
    user.find(ui.button).click()
    await user.should_see("Couldn't search for '1234': unexpected error")
