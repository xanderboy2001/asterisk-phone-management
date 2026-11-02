"""Unit tests for string input validators."""

import string

import pytest
from hypothesis import given
from hypothesis import strategies as st

from asterisk_phone_management.core.exceptions import AsteriskCliError
from asterisk_phone_management.core.validators import (
    ensure_valid,
    normalize_mac_addr,
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
    ("raw", "expected"),
    [
        ("AABBCCDDEEFF", "AABBCCDDEEFF"),
        ("aabbccddeeff", "AABBCCDDEEFF"),
        ("aa:bb:cc:dd:ee:ff", "AABBCCDDEEFF"),
        ("AA-BB-CC-DD-EE-FF", "AABBCCDDEEFF"),
        ("aabb.ccdd.eeff", "AABBCCDDEEFF"),
        ("  aa:bb:cc:dd:ee:ff\n", "AABBCCDDEEFF"),
    ],
)
def test_normalize_mac_addr(raw: str, expected: str) -> None:
    """Separators, case, and surrounding whitespace are normalized."""
    assert normalize_mac_addr(raw) == expected


_HEX_PAIRS = st.lists(
    st.text(alphabet=string.hexdigits, min_size=2, max_size=2),
    min_size=6,
    max_size=6,
)


@given(pairs=_HEX_PAIRS, separator=st.sampled_from(["", ":", "-", "."]))
def test_normalize_mac_addr_valid_macs(
    pairs: list[str], separator: str
) -> None:
    """Every valid MAC normalizes to 12 uppercase hex characters."""
    raw = separator.join(pairs)
    normalized = normalize_mac_addr(raw)
    assert validate_mac_addr(raw) is True
    assert normalized == "".join(pairs).upper()
    assert len(normalized) == 12


@given(raw=st.text())
def test_normalize_mac_addr_is_idempotent(raw: str) -> None:
    """Normalizing twice gives the same result as normalizing once."""
    once = normalize_mac_addr(raw)
    assert normalize_mac_addr(once) == once


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
