"""Unit tests for domain model dataclasses."""

from pathlib import Path

import pytest

from asterisk_phone_management.schemas.models import (
    ActiveCall,
    ConfigMatch,
    Phone,
    Voicemail,
)


def test_config_match_immutability(tmp_path: Path) -> None:
    """Verify ConfigMatch is frozen and immutable.

    Args:
        tmp_path: Pytest temporary directory path.
    """
    match = ConfigMatch(
        file_path=tmp_path / "test.conf", line_number=10, matched_text="data"
    )
    with pytest.raises(AttributeError):
        setattr(match, "line_number", 20)  # ruff: ignore[set-attr-with-constant]


def test_phone_and_voicemail_models() -> None:
    """Verify Phone and Voicemail field properties."""
    phone = Phone(
        extension="1000", mac_address="AABBCCDDEEFF", caller_id="Test"
    )
    vm = Voicemail(name="John", email="john@example.com")

    assert phone.extension == "1000"
    assert phone.mac_address == "AABBCCDDEEFF"
    assert vm.name == "John"
    assert vm.email == "john@example.com"


def test_active_call_field_order() -> None:
    """Verify ActiveCall FIELD_ORDER tuple matches dataclass field count."""
    assert len(ActiveCall.FIELD_ORDER) == 13
    assert ActiveCall.FIELD_ORDER[0] == "channel"
    assert ActiveCall.FIELD_ORDER[-1] == "bridged_channel"
