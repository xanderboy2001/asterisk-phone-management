"""CLI handler functions for processing user menu selections."""

from asterisk_phone_management.cli.prompts import (
    prompt_search_method,
    prompt_use_voicemail,
    read_caller_id,
    read_email,
    read_extension,
    read_mac_addr,
    read_name,
    read_new_password,
    read_search_query,
)
from asterisk_phone_management.core.constants import log
from asterisk_phone_management.schemas.models import Phone, Voicemail
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
    if search_method == "ext":
        return read_extension()
    elif search_method == "mac":
        return read_mac_addr()
    else:
        log.error("Invalid search method: %s", search_method)
        return


def handle_remove_phone() -> None:
    """Prompt for search method and key, then remove a phone."""
    search_method = prompt_search_method()
    search_key = _resolve_search_key(search_method)
    if not search_key:
        return
    remove_phone(search_method, search_key)


def handle_replace_phone() -> None:
    """Prompt for search method and key, then replace phone."""
    search_method = prompt_search_method()
    search_key = _resolve_search_key(search_method)
    if not search_key:
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
