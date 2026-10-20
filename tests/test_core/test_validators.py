"""Unit tests for string input validators."""

import pytest

from asterisk_phone_management.core.exceptions import AsteriskCliError
from asterisk_phone_management.core.validators import (
    ensure_valid,
    validate_caller_id,
    validate_email,
    validate_extension,
    validate_mac_addr,
    validate_vm_field,
    validate_vm_password,
)


@pytest.mark.parametrize(
    ("extension", "expected"),
    [
        ("1234", True),
        ("0000", True),
        ("9999", True),
        ("", "Extension cannot be empty."),
        ("123", "Extension must be 4 digits."),
        ("12345", "Extension must be 4 digits."),
        ("abcd", "Extension must be 4 digits."),
        ("12a4", "Extension must be 4 digits."),
    ],
)
def test_validate_extension(extension: str, expected: bool | str) -> None:
    """Verify extension format validation across valid and invalid strings.

    Args:
        extension: The input extension string under test.
        expected: The expected boolean result or error message.
    """
    result = validate_extension(extension)
    assert result == expected


@pytest.mark.parametrize(
    ("mac_address", "expected"),
    [
        ("AABBCCDDEEFF", True),
        ("aa:bb:cc:dd:ee:ff", True),
        ("AA-BB-CC-DD-EE-FF", True),
        ("aa.bb.cc.dd.ee.ff", True),
        ("1234567890AB", True),
        ("AABBCCDDEEF", "MAC address must be 12 digits."),
        ("AABBCCDDEEFF1", "MAC address must be 12 digits."),
        ("AABBCCDDEEG1", "MAC address must contain hexadecimal characters."),
    ],
)
def test_validate_mac_addr(mac_address: str, expected: bool | str) -> None:
    """Verify MAC address normalization and format validation.

    Args:
        mac_address: The input MAC string under test.
        expected: Expected validation outcome.
    """
    result = validate_mac_addr(mac_address)
    assert result == expected


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("user@example.com", True),
        ("john.doe@sub.domain.org", True),
        ("invalid-email", "Malformed email! Must follow local@domain format."),
        ("@domain.com", "Malformed email! Must follow local@domain format."),
        ("user@", "Malformed email! Must follow local@domain format."),
        (
            "user@domain",
            "Malformed email! Domain name must include a TLD (e.g., .com).",
        ),
        (
            "user@" + "a" * 250 + ".com",
            "Malformed email! Domain name is too long.",
        ),
        (
            "user@invalid_domain.com",
            "Malformed email! Subdomains must be 1-63 chars long and contain only letters, numbers, or internal hyphens.",
        ),
        (
            "user@domain.123",
            "Malformed email! Top-level domain must be at least 2 letters (e.g., .com, .org).",
        ),
    ],
)
def test_validate_email(email: str, expected: bool | str) -> None:
    """Verify email formatting, syntax, and domain structure validation.

    Args:
        email: The email string under test.
        expected: Expected validation outcome.
    """
    result = validate_email(email)
    assert result == expected


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("1234", True),
        ("123456", True),
        ("123", "Password must be at least a 4-digit number."),
        ("abcd", "Password must be at least a 4-digit number."),
        ("12a4", "Password must be at least a 4-digit number."),
    ],
)
def test_validate_vm_password(password: str, expected: bool | str) -> None:
    """Verify voicemail password PIN length and digit validation.

    Args:
        password: The PIN string under test.
        expected: Expected validation outcome.
    """
    result = validate_vm_password(password)
    assert result == expected


@pytest.mark.parametrize(
    ("caller_id", "expected"),
    [
        ('"Jane Example" <1001>', True),
        ("", "Caller ID cannot be empty."),
        ("   ", "Caller ID cannot be empty."),
        (
            '"x"\n[evil](phone)\nsecret=1',
            "Caller ID cannot contain line breaks or semicolons.",
        ),
        ('"x"\r<1001>', "Caller ID cannot contain line breaks or semicolons."),
        (
            '"x"\x00<1001>',
            "Caller ID cannot contain line breaks or semicolons.",
        ),
        (
            '"x" <1001>;note',
            "Caller ID cannot contain line breaks or semicolons.",
        ),
        ("a" * 81, "Caller ID must be at most 80 characters."),
    ],
)
def test_validate_caller_id(caller_id: str, expected: bool | str) -> None:
    """Reject empty, oversized, and line-breaking caller IDs."""
    assert validate_caller_id(caller_id) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Jane Example", True),
        ("jane@example.com", True),
        ("a,b", False),
        ("a|b", False),
        ("a;b", False),
        ("a\nb", False),
    ],
)
def test_validate_vm_field(value: str, expected: bool) -> None:
    """Reject characters that are structural in voicemail.conf."""
    assert (validate_vm_field(value) is True) == expected


def test_ensure_valid_passes_on_true() -> None:
    """A True result does not raise."""
    ensure_valid(result=True)


def test_ensure_valid_raises_message() -> None:
    """An error string is raised as AsteriskCliError."""
    with pytest.raises(AsteriskCliError, match="bad value"):
        ensure_valid("bad value")
