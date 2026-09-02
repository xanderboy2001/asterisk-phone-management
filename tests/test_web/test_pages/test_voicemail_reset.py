"""Tests for the voicemail reset page."""

from unittest.mock import MagicMock

import pytest
from nicegui.testing import User

from asterisk_phone_management.core.exceptions import FileTransactionError
from asterisk_phone_management.web.pages import (
    voicemail_reset as voicemail_page,
)

voicemail_page.register_page()


async def test_voicemail_reset_page_shows_heading_and_input(
    user: User,
) -> None:
    """The voicemail reset page renders its heading and extension input."""
    await user.open("/voicemail-reset")
    await user.should_see("Reset a Voicemail Password")
    await user.should_see("Enter an Extension")


async def test_voicemail_reset_submit_with_no_value_warns(
    user: User,
) -> None:
    """Submitting without an extension shows a 'No data!' notification."""
    await user.open("/voicemail-reset")
    user.find("Submit").click()
    await user.should_see("No data!")


async def test_voicemail_reset_confirm_success(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Confirming resets the voicemail password and shows a success toast."""
    mock_reset = MagicMock()
    monkeypatch.setattr(voicemail_page, "reset_vm_password", mock_reset)
    await user.open("/voicemail-reset")
    user.find("Enter an Extension").type("1234")
    user.find("Submit").click()
    await user.should_see(
        "Are you sure you want to reset the voicemail password for 1234?"
    )
    user.find("Confirm").click()
    await user.should_see("Successfully reset voicemail password for 1234.")
    mock_reset.assert_called_once_with(extension="1234", new_pin="1234")


async def test_voicemail_reset_cancel_does_not_reset(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancelling the confirmation dialog does not reset the password."""
    mock_reset = MagicMock()
    monkeypatch.setattr(voicemail_page, "reset_vm_password", mock_reset)
    await user.open("/voicemail-reset")
    user.find("Enter an Extension").type("1234")
    user.find("Submit").click()
    await user.should_see(
        "Are you sure you want to reset the voicemail password for 1234?"
    )
    user.find("Cancel").click()
    mock_reset.assert_not_called()


async def test_voicemail_reset_failure(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A FileTransactionError is reported via a negative toast."""
    monkeypatch.setattr(
        voicemail_page,
        "reset_vm_password",
        MagicMock(side_effect=FileTransactionError("disk full")),
    )
    await user.open("/voicemail-reset")
    user.find("Enter an Extension").type("1234")
    user.find("Submit").click()
    await user.should_see(
        "Are you sure you want to reset the voicemail password for 1234?"
    )
    user.find("Confirm").click()
    await user.should_see(
        "Failed to reset voicemail password for 1234: disk full"
    )
