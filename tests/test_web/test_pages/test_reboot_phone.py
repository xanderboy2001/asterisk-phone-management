"""Tests for the reboot phone page."""

from unittest.mock import MagicMock

import pytest
from nicegui import ui
from nicegui.testing import User

from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    DeviceCommunicationError,
)
from asterisk_phone_management.web.pages import reboot_phone as reboot_page

reboot_page.register_page()


async def test_reboot_page_shows_heading_and_input(user: User) -> None:
    """The reboot page renders its heading and extension input."""
    await user.open("/reboot-phone")
    await user.should_see("Reboot a Phone")
    await user.should_see("Enter an Extension")


async def test_reboot_submit_with_no_value_warns(user: User) -> None:
    """Submitting without an extension shows a 'No data!' notification."""
    await user.open("/reboot-phone")
    user.find("Submit").click()
    await user.should_see("No data!")


async def test_reboot_confirm_success(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Confirming the dialog reboots the phone and shows a success toast."""
    mock_reboot = MagicMock()
    monkeypatch.setattr(reboot_page, "reboot_phone", mock_reboot)
    await user.open("/reboot-phone")
    user.find("Enter an Extension").type("1234")
    user.find("Submit").click()
    await user.should_see("Are you sure you want to reboot extension 1234?")
    with user.scope(ui.dialog):
        user.find(marker="confirm-yes").click()
    await user.should_see("Successfully sent reboot command to 1234.")
    mock_reboot.assert_called_once_with("1234")


async def test_reboot_cancel_does_not_reboot(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancelling the confirmation dialog does not call reboot_phone."""
    mock_reboot = MagicMock()
    monkeypatch.setattr(reboot_page, "reboot_phone", mock_reboot)
    await user.open("/reboot-phone")
    user.find("Enter an Extension").type("1234")
    user.find("Submit").click()
    await user.should_see("Are you sure you want to reboot extension 1234?")
    with user.scope(ui.dialog):
        user.find(marker="confirm-no").click()
    mock_reboot.assert_not_called()


async def test_reboot_device_communication_error(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DeviceCommunicationError is reported via a negative toast."""
    monkeypatch.setattr(
        reboot_page,
        "reboot_phone",
        MagicMock(side_effect=DeviceCommunicationError("SSH timed out")),
    )
    await user.open("/reboot-phone")
    user.find("Enter an Extension").type("1234")
    user.find("Submit").click()
    await user.should_see("Are you sure you want to reboot extension 1234?")
    with user.scope(ui.dialog):
        user.find(marker="confirm-yes").click()
    await user.should_see("Failed to reboot 1234: SSH timed out")


async def test_reboot_generic_cli_error(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A generic AsteriskCliError is reported via a negative toast."""
    monkeypatch.setattr(
        reboot_page,
        "reboot_phone",
        MagicMock(side_effect=AsteriskCliError("boom")),
    )
    await user.open("/reboot-phone")
    user.find("Enter an Extension").type("1234")
    user.find("Submit").click()
    await user.should_see("Are you sure you want to reboot extension 1234?")
    with user.scope(ui.dialog):
        user.find(marker="confirm-yes").click()
    await user.should_see("An unexpected error occurred: boom")
