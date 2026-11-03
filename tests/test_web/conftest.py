"""Fixtures shared by the web UI tests."""

from collections.abc import Generator

import pytest
from nicegui.testing import User


@pytest.fixture
def expect_error_log(
    user: User, caplog: pytest.LogCaptureFixture
) -> Generator[pytest.LogCaptureFixture]:
    """Allow a test to produce ERROR log records on purpose.

    NiceGUI's ``user`` fixture fails any test that logs at ERROR level.
    Tests of the unexpected-error path log the traceback by design, so
    this fixture clears those records before ``user`` checks them. It
    depends on ``user`` so that it is torn down first.

    Yields:
        The ``caplog`` fixture, for asserting on the logged messages.
    """
    del user
    yield caplog
    # By teardown, caplog has moved on to the teardown phase, so clear the
    # records stored for the test's "call" phase, which ``user`` checks.
    caplog.get_records("call").clear()
