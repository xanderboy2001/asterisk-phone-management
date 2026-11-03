"""Tests for reloading Asterisk after a web change."""

from unittest.mock import MagicMock

import pytest
from nicegui import ui
from nicegui.testing import User

from asterisk_phone_management.core.exceptions import AsteriskServiceError
from asterisk_phone_management.services.device_actions import (
    VOICEMAIL_MODULE,
)
from asterisk_phone_management.web.utils.reload import reload_after_change


@pytest.fixture
def reload_page(user: User) -> User:
    """Register a scratch page with a button that triggers a reload.

    Returns:
        The simulated browser session.
    """

    @ui.page("/__test_reload")
    def _reload_test_page() -> None:
        """Scratch page for exercising reload_after_change."""
        ui.button("Go", on_click=lambda: reload_after_change(VOICEMAIL_MODULE))

    return user


async def _click(user: User) -> None:
    """Open the scratch page and press the button.

    Args:
        user: The simulated browser session.
    """
    await user.open("/__test_reload")
    user.find("Go").click()


async def test_reload_success(
    reload_page: User, mock_reload: MagicMock
) -> None:
    """A successful reload runs the module's command and says so."""
    await _click(reload_page)
    await reload_page.should_see(
        "Asterisk reloaded the voicemail configuration."
    )
    mock_reload.assert_called_once_with(
        command="voicemail reload", friendly_name="voicemail configuration"
    )


async def test_reload_failure_warns(
    reload_page: User, mock_reload: MagicMock
) -> None:
    """A failed reload is a warning that tells the user what to do."""
    mock_reload.side_effect = AsteriskServiceError("Asterisk is not running.")
    await _click(reload_page)
    await reload_page.should_see(
        "Saved, but Asterisk couldn't reload the voicemail configuration."
    )
    await reload_page.should_see("Run Reload Asterisk from the CLI")


@pytest.mark.usefixtures("expect_error_log")
async def test_reload_unexpected_error_warns(
    reload_page: User, mock_reload: MagicMock
) -> None:
    """An unexpected error during reload is still only a warning."""
    mock_reload.side_effect = RuntimeError("bug")
    await _click(reload_page)
    await reload_page.should_see(
        "Saved, but reloading the voicemail configuration failed unexpectedly"
    )
