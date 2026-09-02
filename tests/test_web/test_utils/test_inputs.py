"""Tests for the styled NiceGUI input factory functions."""

import pytest
from nicegui import ui
from nicegui.elements.input import Input
from nicegui.testing import User

from asterisk_phone_management.core.validators import (
    validate_extension,
    validate_mac_addr,
)
from asterisk_phone_management.web.utils.inputs import (
    caller_id_input,
    extension_input,
    mac_address_input,
    styled_input,
)

test_inputs: dict[str, Input] = {}


async def test_inputs_render_with_expected_labels(user: User) -> None:
    """Every input factory renders its configured label."""

    @ui.page("/__test_inputs")
    def _inputs_test_page() -> None:
        """Scratch page rendering every input factory for isolated testing."""
        test_inputs["extension"] = extension_input()
        test_inputs["mac"] = mac_address_input()
        test_inputs["caller_id"] = caller_id_input()
        test_inputs["plain"] = styled_input(label="Plain Field")

    await user.open("/__test_inputs")
    await user.should_see("Enter an Extension")
    await user.should_see("Enter a MAC Address")
    await user.should_see("Enter a Caller ID")
    await user.should_see("Plain Field")


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1234", True),
        ("12", False),
        ("abcd", False),
    ],
)
def test_extension_input_validator_logic(value: str, expected: bool) -> None:
    """Validate extension rules independently of UI runtime context."""
    result = validate_extension(value) if value else True
    assert (result is True) == expected


@pytest.mark.parametrize(
    "value,expected", [("AABBCCDDEEFF", True), ("ZZZZZZZZZZZZ", False)]
)
def test_mac_address_validator_logic(value: str, expected: bool) -> None:
    """Validate MAC address rules independently of UI runtime context."""
    result = validate_mac_addr(value) if value else True
    assert (result is True) == expected
