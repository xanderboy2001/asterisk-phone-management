"""Module for replacing an existing phone in Asterisk configurations.

This script manages the process of updating a phone's hardware address in an
Asterisk environment. It allows searching my extension or MAC address, removes
the old device's TFTP XML configuration file, generates a new TFTP XML file for
the replacement device, updates all references to the old MAC address in
Asterisk configuration files (`sip.conf` and `extensions.conf`),
and reloads Asterisk.
"""

import re
from pathlib import Path

import questionary

from cli import read_extension, read_mac_addr
from config import EXTENSIONS_CONF, SIP_CONF, TFTPBOOT, log
from helpers import (
    backup_config_file,
    get_ext_from_mac,
    get_mac_from_ext,
    safe_exit,
)
from register_phone import generate_cnf_xml
from search_for_extension import ExtensionMatch, search_for_extension
from search_for_mac_address import MACMatch, search_for_mac_address


def replace_mac_in_file(file_path: Path, old_mac: str, new_mac: str) -> None:
    """Replaces all occurrences of a MAC address in a specified config file.

    Args:
        file_path: Path pointing to the file to update.
        old_mac: The original MAC address string to search for.
        new_mac: The new MAC address string to substitute.
    """
    content = file_path.read_text(encoding="utf-8")

    pattern = re.compile(re.escape(old_mac), re.IGNORECASE)
    updated_content = pattern.sub(repl=new_mac, string=content)

    if updated_content == content:
        log.warning(
            "No occurrences of %s found in %s", old_mac, file_path.name
        )
        return

    backups: dict[Path, Path] = {}
    backups[file_path] = backup_config_file(file_path)
    try:
        file_path.write_text(data=updated_content, encoding="utf-8")
        log.info("Updated %s", file_path.name)
    except (PermissionError, OSError) as e:
        log.error("Failed to update %s: %s. Exiting...", file_path.name, e)
        safe_exit(backups=backups if backups else None)


def replace_phone() -> None:
    """Executes the interactive command-line for replacing a phone MAC address.

    Prompts the user to search for a phone entry by extension or MAC address,
    validates the selection, removes the old TFTP `.cnf.xml` file, verifies
    that the replacement MAC address does not already exist, generates a new
    TFTP XML configuration, updates `sip.conf` and `extensions.conf`,
    and reloads Asterisk.

    Raises:
        SystemExit: If no selection choice is provided or if the
            `new_mac_address` is already registered in the system.
    """
    search_method = questionary.select(
        message="Would you like to search by extension or mac address?",
        choices=[
            questionary.Choice(title="Extension", value="ext"),
            questionary.Choice(title="MAC Address", value="mac"),
        ],
        use_shortcuts=True,
    ).ask()

    extension: str = ""
    mac_address: str = ""

    if search_method == "ext":
        extension = read_extension()
        extension_matches: list[ExtensionMatch] = search_for_extension(
            extension
        )
        mac_address = get_mac_from_ext(extension_matches)
    elif search_method == "mac":
        mac_address = read_mac_addr()
        mac_matches: list[MACMatch] = search_for_mac_address(mac_address)
        extension = get_ext_from_mac(mac_matches)
    else:
        log.error("No option selected.")
        raise SystemExit(1)

    old_cnf_file: Path = TFTPBOOT / f"SEP{mac_address}.cnf.xml"
    if old_cnf_file.exists():
        old_cnf_file.unlink()
        log.info("Deleted old .cnf.xml file for SEP%s.", mac_address)
    else:
        log.warning("No old .cnf.xml file found for SEP%s.", mac_address)

    new_mac_address: str = read_mac_addr()
    existing_macs: list[MACMatch] = search_for_mac_address(new_mac_address)
    if existing_macs:
        log.error("Phone with MAC address %s already exists!", new_mac_address)
        raise SystemExit(1)

    generate_cnf_xml(extension=extension, mac_address=new_mac_address)

    for config_file in (SIP_CONF, EXTENSIONS_CONF):
        replace_mac_in_file(
            file_path=config_file, old_mac=mac_address, new_mac=new_mac_address
        )

    log.info("Updated sip.conf and extensions.conf with new MAC address.")

    log.info("Operation completed.")


if __name__ == "__main__":
    replace_phone()
