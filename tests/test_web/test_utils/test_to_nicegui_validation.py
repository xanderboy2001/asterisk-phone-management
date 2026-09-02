"""Tests for the ``to_nicegui_validation`` helper."""

import pytest

from asterisk_phone_management.web.utils.to_nicegui_validation import (
    to_nicegui_validation,
)


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (True, None),
        ("Must be 4 digits.", "Must be 4 digits."),
        (False, "False"),
    ],
)
def test_to_nicegui_validation(
    result: bool | str, expected: str | None
) -> None:
    """True maps to None; anything else maps to its string form."""
    assert to_nicegui_validation(result) == expected
