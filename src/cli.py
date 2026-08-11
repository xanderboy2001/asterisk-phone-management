"""Interactive user prompts."""

import re

import questionary

from config import EXTENSION_LENGTH, MAC_ADDRESS_LENGTH


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


def read_extension() -> str:
    """Prompt the user to enter an extension.

    Returns:
        A validated extension.

    Raises:
        KeyboardInterrupt: If the user cancels the prompt (e.g. Ctrl+C)
    """
    response: str | None = None
    response = questionary.text(
        message="Enter a 4-digit extension (e.g., 1234)",
        validate=validate_extension,
    ).ask()

    if response is None:
        msg = "Prompt cancelled by user."
        raise KeyboardInterrupt(msg)

    return response


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


def read_mac_addr() -> str:
    """Ask the user to enter a MAC address.

    Returns:
        A validated, normalized MAC address (uppercase, no separators).

    Raises:
        KeyboardInterrupt: If the user cancels the prompt (e.g. Ctrl+C).
    """
    response: str | None = None
    response = questionary.text(
        message="Enter a MAC address "
        + "(e.g., AABBCCDDEEFF, AA:BB:CC:DD:EE:FF)",
        validate=validate_mac_addr,
    ).ask()

    if response is None:
        msg = "Prompt cancelled by user."
        raise KeyboardInterrupt(msg)

    return re.sub(r"[:\-.]", "", response).upper()


def read_caller_id(extension: str) -> str:
    """Prompt the user to enter a caller ID.

    Returns:
        A caller ID string.

    Raises:
        KeyboardInterrupt: If the user cancels the prompt (e.g. Ctrl+C).
    """
    response: str | None = None
    response = questionary.text(
        message="Enter a caller ID", default=f'"{extension}" <{extension}>'
    ).ask()

    if response is None:
        msg = "Prompt cancelled by user."
        raise KeyboardInterrupt(msg)

    if not response.endswith(f"<{extension}>"):
        return f"{response} <{extension}>"
    else:
        return response


def read_name() -> str:
    """Prompt the user to enter a name for voicemail.

    Returns:
        The name to use for voicemail.

    Raises:
        KeyboardInterrupt: If the user cancels the prompt (e.g. Ctrl+C).
    """
    response: str | None = None
    response = questionary.text(
        message="Enter a name to use for voicemail"
    ).ask()

    if response is None:
        msg = "Prompt cancelled by user."
        raise KeyboardInterrupt(msg)

    return response.strip()


def validate_email(email: str) -> str | bool:
    """Check whether a given email address is valid.

    Args:
        email: The email to validate.

    Returns:
        True if email is valid, error string otherwise.
    """
    label_regex = re.compile(
        r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
    )
    tld_regex = re.compile(r"^[a-zA-Z]{2,}$")
    email = email.strip()
    parts: list[str] = email.split("@")

    if len(parts) != 2 or not parts[0] or not parts[1]:  # ruff: ignore[magic-value-comparison]
        return "Malformed email! Must follow local@domain format."

    domain_part = parts[1]
    domain_parts: list[str] = domain_part.split(".")

    if len(domain_part) > 253:  # ruff: ignore[magic-value-comparison]
        return "Malformed email! Domain name is too long."

    if len(domain_parts) < 2:  # ruff: ignore[magic-value-comparison]
        return "Malformed email! Domain name must include a TLD (e.g., .com)."

    for label in domain_parts:
        if not label_regex.match(label):
            return (
                "Malformed email! Subdomains must be 1-63 chars long and "
                + "contain only letters, numbers, or internal hyphens."
            )

    tld = domain_parts[-1]
    if not tld_regex.match(tld):
        return (
            "Malformed email! Top-level domain must be at least 2 letters "
            + "(e.g., .com, .org)."
        )

    return True


def read_email() -> str:
    """Prompt the user to enter an email address for voicemail.

    Returns:
        Validated, normalized email string (lowercase).

    Raises:
        KeyboardInterrupt: If the user cancels the prompt (e.g. Ctrl+C).
    """
    response: str | None = None
    response = questionary.text(
        message="Enter an email address to use for voicemail",
        validate=validate_email,
    ).ask()

    if response is None:
        msg = "Prompt cancelled by user."
        raise KeyboardInterrupt(msg)

    return response.strip()
