"""Interactive CLI prompts for user interaction."""

import re
from typing import Literal

import questionary

from asterisk_phone_management.core.constants import (
    MINIMUM_VM_PASSWORD_LENGTH,
    log,
)
from asterisk_phone_management.core.exceptions import AsteriskCliError
from asterisk_phone_management.core.validators import (
    validate_email,
    validate_extension,
    validate_mac_addr,
    validate_vm_password,
)


def read_extension() -> str:
    """Prompt the user to enter an extension.

    Returns:
        A validated extension string.

    Raises:
        KeyboardInterrupt: If the user cancels the prompt (e.g. Ctrl+C)
    """
    response: str | None = questionary.text(
        message="Enter a 4-digit extension (e.g., 1234)",
        validate=validate_extension,
    ).ask()

    if response is None:
        msg = "Prompt cancelled by user."
        raise KeyboardInterrupt(msg)

    return response


def read_mac_addr() -> str:
    """Prompt the user to enter a MAC address.

    Returns:
        A validated, normalized MAC address (uppercase, no separators).

    Raises:
        KeyboardInterrupt: If the user cancels the prompt (e.g. Ctrl+C).
    """
    response: str | None = questionary.text(
        message="Enter a MAC address (e.g., AABBCCDDEEFF, AA:BB:CC:DD:EE:FF)",
        validate=validate_mac_addr,
    ).ask()

    if response is None:
        msg = "Prompt cancelled by user."
        raise KeyboardInterrupt(msg)

    return re.sub(r"[:\-.]", "", response).upper()


def read_caller_id(extension: str) -> str:
    """Prompt the user to enter a caller ID.

    Args:
        extension: The target phone extension.

    Returns:
        A caller ID string.

    Raises:
        KeyboardInterrupt: If the user cancels the prompt (e.g. Ctrl+C).
    """
    response: str | None = questionary.text(
        message="Enter a caller ID", default=f'"{extension}" <{extension}>'
    ).ask()

    if response is None:
        msg = "Prompt cancelled by user."
        raise KeyboardInterrupt(msg)

    if not response.endswith(f"<{extension}>"):
        return f"{response} <{extension}>"
    return response


def read_name() -> str:
    """Prompt the user to enter a name for voicemail.

    Returns:
        The stripped name string for voicemail setup.

    Raises:
        KeyboardInterrupt: If the user cancels the prompt (e.g. Ctrl+C).
    """
    response: str | None = questionary.text(
        message="Enter a name to use for voicemail"
    ).ask()

    if response is None:
        msg = "Prompt cancelled by user."
        raise KeyboardInterrupt(msg)

    return response.strip()


def read_email() -> str:
    """Prompt the user to enter an email address for voicemail.

    Returns:
        Validated, normalized email string (lowercase).

    Raises:
        KeyboardInterrupt: If the user cancels the prompt (e.g. Ctrl+C).
    """
    response: str | None = questionary.text(
        message="Enter an email address to use for voicemail",
        validate=validate_email,
    ).ask()

    if response is None:
        msg = "Prompt cancelled by user."
        raise KeyboardInterrupt(msg)

    return response.strip()


def read_new_password(extension: str) -> str:
    """Read and validate the new voicemail PIN from user input.

    Args:
        extension: The extension for which the new PIN is being set.

    Returns:
        The validated new voicemail PIN.

    Raises:
        AsteriskCliError: If no password is provided.
    """
    new_password = questionary.text(
        message="Enter the new voicemail PIN:",
        default=extension,
        validate=validate_vm_password,
        instruction=(
            "Enter a number at least "
            f"{MINIMUM_VM_PASSWORD_LENGTH} digits long."
        ),
    ).ask()

    if not new_password:
        msg = "No password provided."
        log.error(msg)
        raise AsteriskCliError(msg)

    return new_password


def read_search_query() -> str:
    """Read search query from user input.

    Returns:
        The search query.

    Raises:
        AsteriskCliError: If no search query is provided.
    """
    query = questionary.text(message="Enter the search term:").ask()

    if not query:
        msg = "No search query provided."
        log.error(msg)
        raise AsteriskCliError(msg)

    return query


def prompt_search_method() -> Literal["ext", "mac"]:
    """Prompt user to choose between extension or MAC address search.

    Returns:
        Literal string 'ext' or 'mac'

    Raises:
        AsteriskCliError: If the prompt is cancelled or no selection made.
    """
    search_options: list[questionary.Choice] = [
        questionary.Choice(
            title="Extension",
            description="Find the phone to delete using its extension number.",
            value="ext",
        ),
        questionary.Choice(
            title="MAC Address",
            description="Find the phone to delete using its MAC address.",
            value="mac",
        ),
    ]

    search_method: Literal["ext", "mac"] | None = questionary.select(
        message="How would you like to find the phone to delete?",
        choices=search_options,
    ).ask()

    if not search_method:
        msg = "Prompt cancelled by user."
        log.error(msg)
        raise AsteriskCliError(msg)

    log.debug("Chosen search method: %s", search_method)
    return search_method


def prompt_use_voicemail() -> bool:
    """Prompt the user to opt in to voicemail configuration.

    Returns:
        True if the user wants voicemail configured, False otherwise.
    """
    msg = "Would you like to define a voicemail configuration for this phone?"
    use_voicemail: bool = questionary.confirm(
        message=msg,
        default=False,
        auto_enter=True,
    ).ask()
    log.debug("Using voicemail: %s", use_voicemail)
    return use_voicemail
