"""Prompt user for MAC address and search config files for it."""

import re

import questionary

from globals import MAC_ADDRESS_LENGTH


def validate_mac_addr(mac_address: str) -> bool | str:
    """Check if given MAC address is valid.

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
    """Ask the user to provide an MAC address.

    Returns:
        Validated MAC address.
    """
    response = None
    while response is None:
        response = questionary.text(
            message="Enter a MAC address "
            + "(e.g., AABBCCDDEEFF, AA:BB:CC:DD:EE:FF)",
            validate=validate_mac_addr,
        ).ask()

    return response


if __name__ == "__main__":
    # main()
    pass
