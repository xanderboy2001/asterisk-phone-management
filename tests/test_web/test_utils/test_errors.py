"""Tests for the shared unexpected-error reporter."""

import pytest
from nicegui import ui
from nicegui.testing import User

from asterisk_phone_management.web.utils.errors import report_unexpected_error


async def test_report_unexpected_error_logs_and_notifies(
    user: User, expect_error_log: pytest.LogCaptureFixture
) -> None:
    """The traceback goes to the log; the user sees a short message."""

    @ui.page("/__test_errors")
    def _errors_test_page() -> None:
        """Scratch page that triggers the reporter from an except block."""

        def _boom() -> None:
            try:
                err = "secret internal detail"
                raise RuntimeError(err)
            except RuntimeError:
                report_unexpected_error("do the thing")

        ui.button("Go", on_click=_boom)

    await user.open("/__test_errors")
    user.find("Go").click()

    await user.should_see("Couldn't do the thing: unexpected error")
    await user.should_not_see("secret internal detail")
    log_text = expect_error_log.text
    assert "Unexpected error while trying to do the thing" in log_text
    assert "secret internal detail" in log_text
