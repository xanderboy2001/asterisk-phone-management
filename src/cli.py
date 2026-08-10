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
