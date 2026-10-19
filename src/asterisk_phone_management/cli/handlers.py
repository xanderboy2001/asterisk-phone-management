"""CLI handler functions for processing user menu selections."""

from typing import Literal

import questionary

from asterisk_phone_management.cli.prompts import (
    prompt_search_method,
    prompt_select_call_forwarding_definition,
    prompt_select_caller_id,
    prompt_use_voicemail,
    read_caller_id,
    read_email,
    read_extension,
    read_mac_addr,
    read_name,
    read_new_password,
    read_search_query,
)
from asterisk_phone_management.core.constants import (
    CALLERID_DIRECTIVE,
    SEARCH_BY_EXTENSION,
    SEARCH_BY_MAC,
    SIP_CONF_NAME,
    log,
)
from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
)
from asterisk_phone_management.schemas.models import (
    ConfigMatch,
    Phone,
    Voicemail,
)
from asterisk_phone_management.services.call_forwarding import (
    forwarding_enabled,
    toggle_call_forwarding,
)
from asterisk_phone_management.services.caller_id import edit_caller_id
from asterisk_phone_management.services.device_actions import reboot_phone
from asterisk_phone_management.services.provisioning import (
    register_phone,
    remove_phone,
    replace_phone,
)
from asterisk_phone_management.services.search import (
    search_for_caller_id,
    search_for_extension,
    search_for_mac_address,
)
from asterisk_phone_management.services.voicemail import reset_vm_password


def handle_search_for_extension() -> None:
    """Prompt the user for an extension and search configuration files."""
    ext: str = read_extension()
    search_for_extension(ext)


def handle_search_for_mac_address() -> None:
    """Prompt the user for a MAC address and search configuration files."""
    mac: str = read_mac_addr()
    search_for_mac_address(mac)


def handle_search_for_caller_id() -> None:
    """Prompt the user for a caller ID and search configuration files."""
    caller_id: str = read_search_query()
    search_for_caller_id(caller_id)


def handle_register_phone() -> None:
    """Prompt user for extension and MAC address, then register a new phone."""
    ext: str = read_extension()
    mac: str = read_mac_addr()
    callerid: str = read_caller_id(ext)
    phone = Phone(extension=ext, mac_address=mac, caller_id=callerid)
    voicemail = None

    use_voicemail: bool = prompt_use_voicemail()
    if use_voicemail:
        voicemail = Voicemail(name=read_name(), email=read_email())

    register_phone(phone, voicemail)


def _resolve_search_key(search_method: str) -> str | None:
    """Resolve the search key based on the search method.

    Args:
        search_method: Either "ext" or "mac" to determine which
            input prompt to use.

    Returns:
        The validated search key string, or None if the search
            method is invalid.
    """
    if search_method == SEARCH_BY_EXTENSION:
        return read_extension()
    elif search_method == SEARCH_BY_MAC:
        return read_mac_addr()
    else:
        log.error("Invalid search method: %s", search_method)
        return


def handle_remove_phone() -> None:
    """Prompt for search method and key, then remove a phone."""
    search_method = prompt_search_method()
    search_key = _resolve_search_key(search_method)
    if search_key is None:
        return
    remove_phone(search_method, search_key)


def handle_replace_phone() -> None:
    """Prompt for search method and key, then replace phone."""
    search_method = prompt_search_method()
    search_key = _resolve_search_key(search_method)
    if search_key is None:
        return
    replace_phone(search_method, search_key)


def handle_reset_vm_password() -> None:
    """Prompt for extension and new password, then reset voicemail password."""
    extension = read_extension()
    new_pin = read_new_password(extension)
    reset_vm_password(extension, new_pin)


def handle_reboot_phone() -> None:
    """Prompt for an extension and send reboot signal to phone."""
    ext: str = read_extension()
    reboot_phone(ext)


def handle_edit_caller_id() -> None:
    """Prompt for extension and caller ID, then edit matching entries.

    Raises:
        AsteriskCliError: If no matches are found.
    """
    extension: str = read_extension()
    new_caller_id: str = read_caller_id(extension)

    extension_matches: list[ConfigMatch] = search_for_extension(extension)

    if not extension_matches:
        msg = f"No matches found for {extension}"
        log.error(msg)
        raise AsteriskCliError(msg)

    caller_id_matches: list[ConfigMatch] = [
        match
        for match in extension_matches
        if match.file_path.name == SIP_CONF_NAME
        and match.matched_text.startswith(CALLERID_DIRECTIVE)
    ]
    if not caller_id_matches:
        msg = f"No caller ID(s) found for {extension}"
        log.error(msg)
        raise AsteriskCliError(msg)

    if len(caller_id_matches) == 1:
        targets = caller_id_matches
    else:
        targets = prompt_select_caller_id(caller_id_matches)

    edit_caller_id(targets, new_caller_id)


def handle_toggle_call_forwarding() -> None:
    """Prompt operator to select a user and toggle their call forwarding."""
    user = prompt_select_call_forwarding_definition()
    action: Literal["enable", "disable"]

    if forwarding_enabled(user):
        log.info("True")
        msg = "Call forwarding is enabled. Would you like to disable it?"
        action = "disable"
    else:
        log.info("False")
        msg = "Call forwarding is disabled. Would you like to enable it?"
        action = "enable"

    should_continue = questionary.confirm(msg).ask()

    if should_continue:
        toggle_call_forwarding(user, action)
    else:
        log.warning("User cancelled operation.")
