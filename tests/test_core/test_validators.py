"""Unit tests for string input validators."""

import pytest

from src.core.validators import (
    validate_email,
    validate_extension,
    validate_mac_addr,
    validate_vm_password,
)


@pytest.mark.parametrize(
    ("extension", "expected"),
    [
        ("1234", True),
        ("0000", True),
        ("9999", True),
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
