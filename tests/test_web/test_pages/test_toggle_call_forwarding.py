"""Tests for the toggle call forwarding page."""

from unittest.mock import MagicMock

import pytest
from nicegui.testing import User

from asterisk_phone_management.core.constants import CallForwardingDefinition
from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    AsteriskServiceError,
)
from asterisk_phone_management.web.pages import (
    toggle_call_forwarding as forwarding_page,
)

USER = CallForwardingDefinition(
    name="Buzz Lightyear", extension="1001", forwarding_number="15555550100"
)
forwarding_page.CALL_FORWARDING_USERS = [USER]
forwarding_page.register_page()


async def _submit(user: User) -> None:
    """Open the page, pick the test user, and press Submit.

    Args:
        user: The simulated browser session.
    """
    await user.open("/toggle-call-forwarding")
    user.find("Buzz Lightyear (1001)").click()
    user.find("Submit").click()


@pytest.mark.parametrize(
    ("enabled", "action"), [(False, "enable"), (True, "disable")]
)
async def test_toggle_confirm(
    user: User,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    action: str,
) -> None:
    """Confirming toggles forwarding in the right direction."""
    monkeypatch.setattr(
        forwarding_page, "forwarding_enabled", MagicMock(return_value=enabled)
    )
    mock_toggle = MagicMock()
    monkeypatch.setattr(forwarding_page, "toggle_call_forwarding", mock_toggle)

    await _submit(user)
    await user.should_see(f"Would you like to {action} it?")
    user.find(marker="confirm-yes").click()

    await user.should_see(f"{action.capitalize()}d call forwarding")
    mock_toggle.assert_called_once_with(USER, action=action)


async def test_toggle_cancel(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cancelling changes nothing."""
    monkeypatch.setattr(
        forwarding_page, "forwarding_enabled", MagicMock(return_value=False)
    )
    mock_toggle = MagicMock()
    monkeypatch.setattr(forwarding_page, "toggle_call_forwarding", mock_toggle)

    await _submit(user)
    await user.should_see(marker="confirm-no")
    user.find(marker="confirm-no").click()

    await user.should_see("Cancelled")
    mock_toggle.assert_not_called()


async def test_toggle_failure_is_reported(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A service error is shown to the user."""
    monkeypatch.setattr(
        forwarding_page, "forwarding_enabled", MagicMock(return_value=False)
    )
    monkeypatch.setattr(
        forwarding_page,
        "toggle_call_forwarding",
        MagicMock(side_effect=AsteriskCliError("line changed")),
    )

    await _submit(user)
    await user.should_see(marker="confirm-yes")
    user.find(marker="confirm-yes").click()

    await user.should_see("Failed to enable call forwarding")


@pytest.mark.usefixtures("expect_error_log")
async def test_toggle_unexpected_error_is_reported(
    user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unexpected error while toggling shows a generic message."""
    monkeypatch.setattr(
        forwarding_page, "forwarding_enabled", MagicMock(return_value=False)
    )
    monkeypatch.setattr(
        forwarding_page,
        "toggle_call_forwarding",
        MagicMock(side_effect=RuntimeError("bug")),
    )

    await _submit(user)
    await user.should_see(marker="confirm-yes")
    user.find(marker="confirm-yes").click()

    await user.should_see("Couldn't enable call forwarding")


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (AsteriskCliError("no match"), "Couldn't read call forwarding"),
        (RuntimeError("bug"), "Couldn't read call forwarding"),
    ],
)
@pytest.mark.usefixtures("expect_error_log")
async def test_toggle_state_lookup_failure(
    user: User,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    message: str,
) -> None:
    """If the current state can't be read, no dialog opens."""
    monkeypatch.setattr(
        forwarding_page, "forwarding_enabled", MagicMock(side_effect=error)
    )
    mock_toggle = MagicMock()
    monkeypatch.setattr(forwarding_page, "toggle_call_forwarding", mock_toggle)

    await _submit(user)

    await user.should_see(message)
    await user.should_not_see(marker="confirm-yes")
    mock_toggle.assert_not_called()


async def test_toggle_without_selection_warns(user: User) -> None:
    """Submitting with nobody selected shows a warning."""
    await user.open("/toggle-call-forwarding")
    user.find("Submit").click()
    await user.should_see("No user selected!")


async def test_toggle_reloads_dialplan(
    user: User, monkeypatch: pytest.MonkeyPatch, mock_reload: MagicMock
) -> None:
    """A successful toggle reloads the dialplan (F-17)."""
    monkeypatch.setattr(
        forwarding_page, "forwarding_enabled", MagicMock(return_value=False)
    )
    monkeypatch.setattr(forwarding_page, "toggle_call_forwarding", MagicMock())
    await _submit(user)
    await user.should_see(marker="confirm-yes")
    user.find(marker="confirm-yes").click()
    await user.should_see("Asterisk reloaded the dialplan.")
    mock_reload.assert_called_once_with(
        command="dialplan reload", friendly_name="dialplan"
    )


async def test_toggle_failure_does_not_reload(
    user: User, monkeypatch: pytest.MonkeyPatch, mock_reload: MagicMock
) -> None:
    """A failed toggle doesn't reload Asterisk."""
    monkeypatch.setattr(
        forwarding_page, "forwarding_enabled", MagicMock(return_value=False)
    )
    monkeypatch.setattr(
        forwarding_page,
        "toggle_call_forwarding",
        MagicMock(side_effect=AsteriskCliError("line changed")),
    )
    await _submit(user)
    await user.should_see(marker="confirm-yes")
    user.find(marker="confirm-yes").click()
    await user.should_see("Failed to enable call forwarding")
    mock_reload.assert_not_called()


async def test_toggle_reload_failure_keeps_success(
    user: User, monkeypatch: pytest.MonkeyPatch, mock_reload: MagicMock
) -> None:
    """If the reload fails, the toggle still reports success plus a warning."""
    monkeypatch.setattr(
        forwarding_page, "forwarding_enabled", MagicMock(return_value=False)
    )
    monkeypatch.setattr(forwarding_page, "toggle_call_forwarding", MagicMock())
    mock_reload.side_effect = AsteriskServiceError("Asterisk is not running.")
    await _submit(user)
    await user.should_see(marker="confirm-yes")
    user.find(marker="confirm-yes").click()
    await user.should_see("Enabled call forwarding")
    await user.should_see("Saved, but Asterisk couldn't reload the dialplan.")
