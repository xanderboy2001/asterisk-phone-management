"""Interactive CLI prompts for user interaction."""

import re
from typing import TypeVar

import questionary
from questionary import Choice

from asterisk_phone_management.core.constants import (
    CALL_FORWARDING_USERS,
    MINIMUM_VM_PASSWORD_LENGTH,
    SEARCH_BY_EXTENSION,
    SEARCH_BY_MAC,
    CallForwardingDefinition,
    SearchMethod,
    log,
)
from asterisk_phone_management.core.exceptions import AsteriskCliError
from asterisk_phone_management.core.validators import (
    validate_caller_id,
    validate_email,
    validate_extension,
    validate_mac_addr,
    validate_vm_field,
    validate_vm_password,
)
from asterisk_phone_management.schemas.models import ConfigMatch

T = TypeVar("T")


def ask(question: questionary.Question, expected: type[T]) -> T:
    """Ask a question, treating cancellation and wrong types as errors.

    Args:
        question: The questionary prompt to ask.
        expected: The type the answer must be.

    Returns:
        The answer, narrowed to ``expected``.

    Raises:
        KeyboardInterrupt: If the user cancels the prompt.
        AsteriskCliError: If the answer is not of the expected type.
    """
    answer: object = question.ask()
    if answer is None:
        msg = "Prompt cancelled by user."
        raise KeyboardInterrupt(msg)
    if not isinstance(answer, expected):
        msg = f"Unexpected answer type: {type(answer).__name__}"
        raise AsteriskCliError(msg)
    return answer


def read_extension() -> str:
    """Prompt the user to enter an extension.

    Returns:
        A validated extension string.
    """
    question: questionary.Question = questionary.text(
        message="Enter a 4-digit extension (e.g., 1234)",
        validate=validate_extension,
    )

    return ask(question=question, expected=str)


def read_mac_addr() -> str:
    """Prompt the user to enter a MAC address.

    Returns:
        A validated, normalized MAC address (uppercase, no separators).
    """
    question: questionary.Question = questionary.text(
        message="Enter a MAC address (e.g., AABBCCDDEEFF, AA:BB:CC:DD:EE:FF)",
        validate=validate_mac_addr,
    )

    response: str = ask(question=question, expected=str)

    return re.sub(r"[:\-.]", "", response).upper()


def read_caller_id(extension: str) -> str:
    """Prompt the user to enter a caller ID.

    Args:
        extension: The target phone extension.

    Returns:
        A caller ID string.
    """
    question: questionary.Question = questionary.text(
        message="Enter a caller ID",
        default=f'"{extension}" <{extension}>',
        validate=validate_caller_id,
    )
    response: str = ask(question=question, expected=str)

    if not response.endswith(f"<{extension}>"):
        return f"{response} <{extension}>"
    return response


def read_name() -> str:
    """Prompt the user to enter a name for voicemail.

    Returns:
        The stripped name string for voicemail setup.
    """
    response: str = ask(
        questionary.text(
            message="Enter a name to use for voicemail",
            validate=validate_vm_field,
        ),
        str,
    )
    return response.strip()


def _validate_vm_email(email: str) -> bool | str:
    """Validate an email for both format and voicemail.conf safety.

    Args:
        email: The email address to validate.

    Returns:
        True if the email is valid, otherwise an error message.
    """
    field_result = validate_vm_field(email)
    if field_result is not True:
        return field_result
    return validate_email(email)


def read_email() -> str:
    """Prompt the user to enter an email address for voicemail.

    Returns:
        Validated, normalized email string (lowercase).
    """
    response: str = ask(
        questionary.text(
            message="Enter an email address to use for voicemail",
            validate=_validate_vm_email,
        ),
        str,
    )
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
    new_password: str = ask(
        questionary.text(
            message="Enter the new voicemail PIN:",
            default=extension,
            validate=validate_vm_password,
            instruction=(
                "Enter a number at least "
                f"{MINIMUM_VM_PASSWORD_LENGTH} digits long."
            ),
        ),
        str,
    )
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
    query: str = ask(
        questionary.text(message="Enter the search term:"), str
    ).strip()
    if not query:
        msg = "No search query provided."
        log.error(msg)
        raise AsteriskCliError(msg)
    return query


def prompt_search_method() -> SearchMethod:
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
            value=SEARCH_BY_EXTENSION,
        ),
        questionary.Choice(
            title="MAC Address",
            description="Find the phone to delete using its MAC address.",
            value=SEARCH_BY_MAC,
        ),
    ]

    answer: str = ask(
        questionary.select(
            message="How would you like to find the phone to delete?",
            choices=search_options,
        ),
        str,
    )
    if answer == SEARCH_BY_EXTENSION:
        search_method: SearchMethod = SEARCH_BY_EXTENSION
    elif answer == SEARCH_BY_MAC:
        search_method: SearchMethod = SEARCH_BY_MAC
    else:
        msg = f"Unknown search method: {answer}"
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
    use_voicemail: bool = ask(
        questionary.confirm(
            message=msg,
            default=False,
            auto_enter=True,
        ),
        bool,
    )
    log.debug("Using voicemail: %s", use_voicemail)
    return use_voicemail


def prompt_select_caller_id(matches: list[ConfigMatch]) -> list[ConfigMatch]:
    """Prompt user to select specific caller ID entries from matches.

    Args:
        matches: List of ConfigMatch instances to choose from.

    Returns:
        List of selected ConfigMatch instances.

    Raises:
        KeyboardInterrupt: If the user cancels the selection.
    """
    action: str = ask(
        questionary.select(
            message=(
                "Multiple caller ID entries found. "
                "How would you like to proceed?"
            ),
            choices=[
                questionary.Choice(
                    title="Update all occurrences", value="all"
                ),
                questionary.Choice(
                    title="Select specific entries to update", value="select"
                ),
                questionary.Choice(title="Cancel operation", value="cancel"),
            ],
        ),
        str,
    )

    if action == "cancel":
        msg = "Prompt cancelled by user"
        raise KeyboardInterrupt(msg)

    if action == "all":
        return matches

    choices: list[questionary.Choice] = [
        questionary.Choice(
            title=f"Line {m.line_number}: {m.matched_text}", value=m
        )
        for m in matches
    ]
    selected_matches: list[ConfigMatch] = ask(
        questionary.checkbox(
            message="Select the caller ID entries to update:",
            choices=choices,
            validate=lambda selected: (
                True if selected else "Select at least one entry."
            ),
        ),
        list,
    )
    if not selected_matches:
        msg = "Prompt cancelled by user"
        raise KeyboardInterrupt(msg)
    return selected_matches


def prompt_select_call_forwarding_definition() -> CallForwardingDefinition:
    """Prompt the operator to pick a user from the configured roster.

    Returns:
        The selected user's call forwarding definition.

    Raises:
        AsteriskCliError: If the user cancels the prompt.
    """
    if not CALL_FORWARDING_USERS:
        msg = "No call forwarding users configured."
        log.error(msg)
        raise AsteriskCliError(msg)
    choices: list[Choice] = [
        Choice(
            title=f"{user.name} ({user.extension})",
            value=user,
        )
        for user in CALL_FORWARDING_USERS
    ]
    return ask(
        questionary.select(message="Choose a user:", choices=choices),
        CallForwardingDefinition,
    )
