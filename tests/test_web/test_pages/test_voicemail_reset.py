"""Tests for the voicemail reset page."""

from unittest.mock import MagicMock

import pytest
from nicegui.testing import User

from asterisk_phone_management.core.exceptions import (
    AsteriskServiceError,
    FileTransactionError,
)
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
    user.find(marker="confirm-yes").click()
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
    user.find(marker="confirm-no").click()
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
    user.find(marker="confirm-yes").click()
    await user.should_see(
        "Failed to reset voicemail password for 1234: disk full"
    )


async def test_voicemail_reset_invalid_extension_is_rejected(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A partial extension is rejected before the confirm dialog opens."""
    mock_service = MagicMock()
    monkeypatch.setattr(voicemail_page, "reset_vm_password", mock_service)
    await user.open("/voicemail-reset")
    user.find("Enter an Extension").type("1")
    user.find("Submit").click()
    await user.should_see("Extension must be 4 digits.")
    await user.should_not_see(marker="confirm-yes")
    mock_service.assert_not_called()


@pytest.mark.usefixtures("expect_error_log")
async def test_voicemail_reset_unexpected_error_is_reported(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unexpected error shows a generic message, not a silent failure."""
    monkeypatch.setattr(
        voicemail_page,
        "reset_vm_password",
        MagicMock(side_effect=RuntimeError("bug")),
    )
    await user.open("/voicemail-reset")
    user.find("Enter an Extension").type("1234")
    user.find("Submit").click()
    await user.should_see(marker="confirm-yes")
    user.find(marker="confirm-yes").click()
    await user.should_see(
        "Couldn't reset the voicemail password for 1234: unexpected error"
    )


async def _confirm_reset(user: User) -> None:
    """Submit extension 1234 and confirm the dialog.

    Args:
        user: The simulated browser session.
    """
    await user.open("/voicemail-reset")
    user.find("Enter an Extension").type("1234")
    user.find("Submit").click()
    await user.should_see(marker="confirm-yes")
    user.find(marker="confirm-yes").click()


async def test_voicemail_reset_reloads_voicemail(
    user: User, monkeypatch: pytest.MonkeyPatch, mock_reload: MagicMock
) -> None:
    """A successful reset reloads voicemail, and nothing else (F-17)."""
    monkeypatch.setattr(voicemail_page, "reset_vm_password", MagicMock())
    await _confirm_reset(user)
    await user.should_see("Asterisk reloaded the voicemail configuration.")
    mock_reload.assert_called_once_with(
        command="voicemail reload", friendly_name="voicemail configuration"
    )


async def test_voicemail_reset_failure_does_not_reload(
    user: User, monkeypatch: pytest.MonkeyPatch, mock_reload: MagicMock
) -> None:
    """A failed reset doesn't reload Asterisk."""
    monkeypatch.setattr(
        voicemail_page,
        "reset_vm_password",
        MagicMock(side_effect=FileTransactionError("disk full")),
    )
    await _confirm_reset(user)
    await user.should_see("Failed to reset voicemail password")
    mock_reload.assert_not_called()


async def test_voicemail_reset_cancel_does_not_reload(
    user: User, monkeypatch: pytest.MonkeyPatch, mock_reload: MagicMock
) -> None:
    """Cancelling doesn't reload Asterisk."""
    mock_reset = MagicMock()
    monkeypatch.setattr(voicemail_page, "reset_vm_password", mock_reset)
    await user.open("/voicemail-reset")
    user.find("Enter an Extension").type("1234")
    user.find("Submit").click()
    await user.should_see(marker="confirm-no")
    user.find(marker="confirm-no").click()
    mock_reset.assert_not_called()
    mock_reload.assert_not_called()


async def test_voicemail_reset_reload_failure_keeps_success(
    user: User, monkeypatch: pytest.MonkeyPatch, mock_reload: MagicMock
) -> None:
    """If the reload fails, the reset still reports success plus a warning."""
    monkeypatch.setattr(voicemail_page, "reset_vm_password", MagicMock())
    mock_reload.side_effect = AsteriskServiceError("Asterisk is not running.")
    await _confirm_reset(user)
    await user.should_see("Successfully reset voicemail password for 1234.")
    await user.should_see("Saved, but Asterisk couldn't reload")


async def test_voicemail_reset_states_pin_policy(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dialog and the success message both state the new PIN (F-19)."""
    mock_reset = MagicMock()
    monkeypatch.setattr(voicemail_page, "reset_vm_password", mock_reset)
    await user.open("/voicemail-reset")
    user.find("Enter an Extension").type("1234")
    user.find("Submit").click()

    await user.should_see("The new PIN will be 1234, the extension number.")
    user.find(marker="confirm-yes").click()

    await user.should_see("The new PIN is 1234.")
    mock_reset.assert_called_once_with(extension="1234", new_pin="1234")
