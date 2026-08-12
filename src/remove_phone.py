"""Removes/deregisters a CISCO Phone from the Asterisk PBX phone system."""

from pathlib import Path

import questionary
from questionary import Choice
from rich.table import Table

from cli import read_extension, read_mac_addr
from config import (
    EXTENSIONS_CONF,
    SIP_CONF,
    TFTPBOOT,
    VOICEMAIL_CONF,
    console,
    log,
)
from helpers import (
    backup_config_file,
    get_ext_from_mac,
    get_mac_from_ext,
    safe_exit,
)
from reload_asterisk import reload_asterisk
from search_for_extension import ExtensionMatch, search_for_extension
from search_for_mac_address import MACMatch, search_for_mac_address


def print_phone_information(extension: str, mac_address: str) -> None:
    """Prints the phone information in a formatted table.

    Args:
        extension: The phone extension number.
        mac_address: The phone MAC address.
    """
    table = Table(title="Phone Information")
    table.add_column("Extension")
    table.add_column("MAC Address")
    table.add_row(extension, mac_address)
    console.print(table)


def _remove_cnf_xml(file_path: Path) -> None:
    if file_path.suffixes != [".cnf", ".xml"]:
        log.error("Provided file is not a .cnf.xml file!")
        raise SystemExit

    try:
        file_path.unlink()
        log.debug("Deleted %s!", file_path)
    except PermissionError as e:
        log.error("Invalid permissions to delete %s", file_path)
        raise SystemExit from e
    except OSError as e:
        log.error("OS error when deleting %s", file_path)
        raise SystemExit from e


def _remove_sip_section(sip_conf: Path, mac_address: str) -> None:
    content = sip_conf.read_text(encoding="utf-8")
    lines: list[str] = content.splitlines()
    new_lines: list[str] = []
    skip: bool = False

    target_header: str = f"[SEP{mac_address}]".upper()

    for line in lines:
        stripped: str = line.strip()
        if stripped.startswith("["):
            skip = stripped.upper().startswith(target_header)

        if not skip:
            new_lines.append(line)

    sip_conf.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    log.debug("Removed section %s from %s", target_header, sip_conf.name)


def _remove_extension_lines(ext_conf: Path, extension: str) -> None:
    content = ext_conf.read_text(encoding="utf-8")
    lines = content.splitlines()
    new_lines = [
        line
        for line in lines
        if not line.strip().startswith(f"exten => {extension}")
    ]
    ext_conf.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    log.debug("Removed extension %s entries from %s", extension, ext_conf.name)


def _remove_voicemail_entry(vm_conf: Path, extension: str) -> None:
    content = vm_conf.read_text(encoding="utf-8")
    lines = content.splitlines()
    new_lines = [
        line for line in lines if not line.strip().startswith(extension)
    ]
    vm_conf.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    log.debug("Removed voicemail box %s from %s", extension, vm_conf.name)


def _deprovision_phone(extension: str, mac_address: str) -> None:
    xml_path = TFTPBOOT / f"SEP{mac_address}.cnf.xml"

    backups: dict[Path, Path] = {}

    try:
        backups[SIP_CONF] = backup_config_file(SIP_CONF)
        backups[EXTENSIONS_CONF] = backup_config_file(EXTENSIONS_CONF)
        backups[VOICEMAIL_CONF] = backup_config_file(VOICEMAIL_CONF)
    except OSError as err:
        log.error("File system error during backup creation: %s", err)
        safe_exit(backups=backups)

    try:
        _remove_sip_section(SIP_CONF, mac_address)
        _remove_extension_lines(EXTENSIONS_CONF, extension)
        _remove_voicemail_entry(VOICEMAIL_CONF, extension)
        _remove_cnf_xml(xml_path)

        log.info(
            "Successfully deprovisioned phone (Extension: %s, MAC: %s)",
            extension,
            mac_address,
        )
    except OSError as err:
        log.error("File system error during phone deprovisioning: %s", err)
        safe_exit(backups=backups)


def remove_phone() -> None:
    """Prompts the user to search for and delete an existing phone config."""
    search_options: list[Choice] = [
        Choice(
            title="Extension",
            description="Find the phone to delete using its extension number.",
            value="ext",
        ),
        Choice(
            title="MAC Address",
            description="Find the phone to delete using its MAC address.",
            value="mac",
        ),
    ]

    search_method: str = questionary.select(
        message="How would you like to find the phone to delete?",
        choices=search_options,
    ).ask()

    if not search_method:
        log.error("Prompt cancelled by user.")
        return

    log.debug(f"Chosen search method: {search_method}")

    extension: str = ""
    mac_address: str = ""
    found: list[ExtensionMatch] | list[MACMatch] = []

    if search_method == "ext":
        extension = read_extension()
        found = search_for_extension(extension)
        if not found:
            return
        mac_address = get_mac_from_ext(matches=found)
    elif search_method == "mac":
        mac_address = read_mac_addr()
        found = search_for_mac_address(mac_address)
        if not found:
            return
        extension = get_ext_from_mac(matches=found)

    print_phone_information(extension, mac_address)

    should_continue: bool = questionary.confirm(
        message="Are you sure you wish to delete/deregister this phone?",
        default=False,
    ).ask()

    if not should_continue:
        log.error("User cancelled interaction.")
        return

    _deprovision_phone(extension, mac_address)


if __name__ == "__main__":
    remove_phone()
    reload_asterisk()
