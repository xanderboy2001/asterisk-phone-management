"""Validation functions for extensions, MAC addresses, emails, and PINs."""

import re

from asterisk_phone_management.core.globals import (
    EXTENSION_LENGTH,
    MAC_ADDRESS_LENGTH,
    MINIMUM_VM_PASSWORD_LENGTH,
)

_EMAIL_PARTS_COUNT: int = 2
_MAX_DOMAIN_LENGTH: int = 253
_MIN_DOMAIN_LABELS: int = 2

_LABEL_REGEX = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")
_TLD_REGEX = re.compile(r"^[a-zA-Z]{2,}$")


def validate_extension(extension: str) -> bool | str:
    """Check whether a given extension is valid.

    Args:
        extension: The extension to validate.

    Returns:
        True if extension is valid, otherwise an error message.
    """
    if len(extension) != EXTENSION_LENGTH or not extension.isdigit():
        return f"Extension must be {EXTENSION_LENGTH} digits."

    return True


def validate_mac_addr(mac_address: str) -> bool | str:
    """Check whether a given MAC address is valid.

    Args:
        mac_address: The MAC address to validate.

    Returns:
        True if the MAC address is valid, otherwise an error message.
    """
    raw_mac: str = re.sub(r"[:\-.]", "", mac_address).upper()
    if len(raw_mac) != MAC_ADDRESS_LENGTH:
        return "MAC address must be 12 digits."

    if not re.fullmatch(r"^[0-9A-F]{12}$", raw_mac):
        return "MAC address must contain hexadecimal characters."

    return True


def validate_email(email: str) -> str | bool:
    """Check whether a given email address is valid.

    Args:
        email: The email to validate.

    Returns:
        True if email is valid, error string otherwise.
    """
    email = email.strip()
    parts: list[str] = email.split("@")

    if len(parts) != _EMAIL_PARTS_COUNT or not parts[0] or not parts[1]:
        return "Malformed email! Must follow local@domain format."

    domain_part = parts[1]
    domain_parts: list[str] = domain_part.split(".")

    if len(domain_part) > _MAX_DOMAIN_LENGTH:
        return "Malformed email! Domain name is too long."

    if len(domain_parts) < _MIN_DOMAIN_LABELS:
        return "Malformed email! Domain name must include a TLD (e.g., .com)."

    for label in domain_parts:
        if not _LABEL_REGEX.match(label):
            return (
                "Malformed email! Subdomains must be 1-63 chars long and "
                "contain only letters, numbers, or internal hyphens."
            )

    tld = domain_parts[-1]
    if not _TLD_REGEX.match(tld):
        return (
            "Malformed email! Top-level domain must be at least 2 letters "
            "(e.g., .com, .org)."
        )

    return True


def validate_vm_password(password: str) -> bool | str:
    """Validate the voicemail password.

    Args:
        password: The new voicemail password to validate.

    Returns:
        True if the password is valid,
            otherwise a string with an error message.
    """
    if len(password) < MINIMUM_VM_PASSWORD_LENGTH or not password.isdigit():
        return (
            "Password must be at least a "
            f"{MINIMUM_VM_PASSWORD_LENGTH}-digit number."
        )
    return True
