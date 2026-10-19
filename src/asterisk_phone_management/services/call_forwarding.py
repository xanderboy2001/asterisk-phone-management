"""Call Forwarding Module to enable/disable call forwarding for users."""

from typing import Literal

from asterisk_phone_management.core.constants import (
    CallForwardingDefinition,
    log,
)
from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    AsteriskServiceError,
)
from asterisk_phone_management.core.transactions import ConfigTransaction
from asterisk_phone_management.helpers import get_call_forwarding_config
from asterisk_phone_management.schemas.models import ConfigMatch


def forwarding_enabled(user: CallForwardingDefinition) -> bool:
    """Determine whether call forwarding is currently active.

    Args:
        user: The user whose forwarding state is being checked.

    Returns:
        True if forwarding is enabled, False if it is disabled.
    """
    matched_text = get_call_forwarding_config(user).matched_text
    forwarding_string: str = f"&SIP/{user.forwarding_number}@cisco_vg"

    return not matched_text.endswith(f";{forwarding_string}")


def _build_forwarding_string(user: CallForwardingDefinition) -> str:
    """Build the Asterisk dial string used to forward calls to a user.

    Args:
        user: The user whose forwarding number should be encoded.

    Returns:
        The ``&SIP/<number>@cisco_vg`` fragment used in ``extensions.conf``.
    """
    return f"&SIP/{user.forwarding_number}@cisco_vg"


def _enable_forwarding_text(
    matched_text: str, user: CallForwardingDefinition
) -> str:
    """Build the enabled form of a matched ``extensions.conf`` line.

    Moves the forwarding fragment from its commented-out position after the
    closing parenthesis to just before the first comma inside ``Dial(...)``,
    so Asterisk dials both the desk phone and the forwarding number.

    Args:
        matched_text: The current (disabled) line contents.
        user: The user whose call forwarding is being enabled.

    Returns:
        The updated line contents with call forwarding enabled.

    Raises:
        AsteriskServiceError: If the line is not currently disabled.
    """
    forwarding_string: str = _build_forwarding_string(user)
    disabled_suffix: str = f";{forwarding_string}"

    if not matched_text.endswith(disabled_suffix):
        msg = f"Call forwarding is already enabled for {user.name}."
        log.error(msg)
        raise AsteriskServiceError(msg)

    base_text: str = matched_text.removesuffix(disabled_suffix)
    open_paren_index: int = base_text.index("(")
    first_comma_index: int = base_text.index(",", open_paren_index)

    return (
        f"{base_text[:first_comma_index]}"
        f"{forwarding_string}"
        f"{base_text[first_comma_index:]}"
    )


def _disable_forwarding_text(
    matched_text: str, user: CallForwardingDefinition
) -> str:
    """Build the disabled form of a matched ``extensions.conf`` line.

    Moves the forwarding fragment out of ``Dial(...)`` and appends it after
    the closing parenthesis behind a semicolon, which comments it out.

    Args:
        matched_text: The current (enabled) line contents.
        user: The user whose call forwarding is being disabled.

    Returns:
        The updated line contents with call forwarding disabled.

    Raises:
        AsteriskServiceError: If the line is not currently enabled.
    """
    forwarding_string: str = _build_forwarding_string(user)

    if forwarding_string not in matched_text or matched_text.endswith(
        f";{forwarding_string}"
    ):
        msg = f"Call forwarding is already disabled for {user.name}."
        log.error(msg)
        raise AsteriskServiceError(msg)

    base_text: str = matched_text.replace(forwarding_string, "", 1)

    return f"{base_text};{forwarding_string}"


def _write_config_update(
    match: ConfigMatch, old_text: str, new_text: str
) -> None:
    """Persist an updated line to its source config file.

    Args:
        match: The config match identifying the file and line to update.
        old_text: The exact text currently on that line to be replaced.
        new_text: The text to replace it with.

    Raises:
        AsteriskCliError: If the expected text is not found on that line.
    """
    lines: list[str] = match.file_path.read_text(encoding="utf-8").splitlines(
        keepends=True
    )
    line_index: int = match.line_number - 1

    if old_text not in lines[line_index]:
        msg = (
            f"Expected text not found on line {match.line_number} "
            f"of {match.file_path}."
        )
        log.error(msg)
        raise AsteriskCliError(msg)

    lines[line_index] = lines[line_index].replace(old_text, new_text, 1)
    match.file_path.write_text("".join(lines), encoding="utf-8")
    log.info(f"Updated {match.file_path} at line {match.line_number}.")


def toggle_call_forwarding(
    user: CallForwardingDefinition, action: Literal["enable", "disable"]
) -> None:
    """Enable or disable call forwarding for a given user.

    Args:
        user: The user whose call forwarding should be toggled.
        action: The action to take. Either 'enable' or 'disable'.
    """
    match = get_call_forwarding_config(user)
    new_text: str = (
        _disable_forwarding_text(match.matched_text, user)
        if action == "disable"
        else _enable_forwarding_text(match.matched_text, user)
    )
    with ConfigTransaction([match.file_path]):
        _write_config_update(match, match.matched_text, new_text)
