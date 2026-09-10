"""Provisioning, deprovisioning, and MAC-replacement services for phones."""

import re
from collections.abc import Iterable
from pathlib import Path

import questionary

from asterisk_phone_management.cli.prompts import read_mac_addr
from asterisk_phone_management.cli.views import print_phone_table
from asterisk_phone_management.core.constants import (
    EXTENSIONS_CONF,
    MAILBOX_CONTEXT,
    SEARCH_BY_EXTENSION,
    SEARCH_BY_MAC,
    SEP_PREFIX,
    SIP_CONF,
    TFTPBOOT,
    VOICEMAIL_CONF,
    XML_CONFIG_EXTENSION,
    XML_TEMPLATE,
    log,
)
from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    AsteriskServiceError,
    FileTransactionError,
)
from asterisk_phone_management.core.transactions import ConfigTransaction
from asterisk_phone_management.helpers import (
    copy_file_safe,
    get_caller_id_from_ext,
    get_ext_from_mac,
    get_mac_from_ext,
)
from asterisk_phone_management.schemas.models import (
    ConfigMatch,
    Phone,
    Voicemail,
)
from asterisk_phone_management.services.search import (
    search_for_extension,
    search_for_mac_address,
)


def _patch_cnf_xml(file_path: Path, placeholder: str, new_value: str) -> None:
    """Replace placeholder text in a .cnf.xml configuration file.

    Args:
        file_path: Path to the .cnf.xml file.
        placeholder: Text template string to replace.
        new_value: Value to insert into the file.
    """
    content: str = file_path.read_text(encoding="utf-8")
    updated_content: str = content.replace(placeholder, new_value)
    file_path.write_text(data=updated_content, encoding="utf-8")


def _remove_cnf_xml(file_path: Path) -> None:
    """Delete a specified .cnf.xml configuration file.

    Args:
        file_path: Target path of the file to unlink.

    Raises:
        AsteriskCliError: If the file's extension is not .cnf.xml.
        FileTransactionError: If deletion fails due to permissions or
            another OS-level error.
    """
    if file_path.suffixes != [".cnf", ".xml"]:
        msg = "Provided file is not a .cnf.xml file!"
        log.error(msg)
        raise AsteriskCliError(msg)

    try:
        file_path.unlink()
        log.debug("Deleted %s!", file_path)
    except PermissionError as e:
        msg = f"Invalid permissions to delete {file_path}"
        log.error(msg)
        raise FileTransactionError(msg) from e
    except OSError as e:
        msg = f"OS error when deleting {file_path}"
        log.error(msg)
        raise FileTransactionError(msg) from e


def _remove_sip_section(sip_conf: Path, mac_address: str) -> None:
    """Remove a SIP device section from sip.conf based on MAC address.

    Args:
        sip_conf: Path to sip.conf.
        mac_address: MAC address of device section to purge.
    """
    content = sip_conf.read_text(encoding="utf-8")
    lines: list[str] = content.splitlines()
    new_lines: list[str] = []
    skip: bool = False

    target_header: str = f"[{SEP_PREFIX}{mac_address}]".upper()

    for line in lines:
        stripped: str = line.strip()
        if stripped.startswith("["):
            skip = stripped.upper().startswith(target_header)

        if not skip:
            new_lines.append(line)

    sip_conf.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    log.debug("Removed section %s from %s", target_header, sip_conf.name)


def _remove_extension_lines(ext_conf: Path, extension: str) -> None:
    """Remove dialplan extension entries from extensions.conf.

    Args:
        ext_conf: Path to extensions.conf.
        extension: Target extension number to remove.
    """
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
    """Remove a voicemail box entry from voicemail.conf.

    Args:
        vm_conf: Path to voicemail.conf.
        extension: Extension box number to purge.
    """
    content = vm_conf.read_text(encoding="utf-8")
    lines = content.splitlines()
    new_lines = [
        line for line in lines if not line.strip().startswith(extension)
    ]
    vm_conf.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    log.debug("Removed voicemail box %s from %s", extension, vm_conf.name)


def _deprovision_phone(extension: str, mac_address: str) -> None:
    """Deprovision a phone across all system config files and delete XML.

    Args:
        extension: The phone extension.
        mac_address: The MAC address.

    Raises:
        AsteriskServiceError: If any part of deprovisioning fails. The
            three config files are rolled back to their prior state
            before this is raised.
    """
    xml_path = TFTPBOOT / f"{SEP_PREFIX}{mac_address}{XML_CONFIG_EXTENSION}"

    try:
        with ConfigTransaction((SIP_CONF, EXTENSIONS_CONF, VOICEMAIL_CONF)):
            _remove_sip_section(SIP_CONF, mac_address)
            _remove_extension_lines(EXTENSIONS_CONF, extension)
            _remove_voicemail_entry(VOICEMAIL_CONF, extension)
            _remove_cnf_xml(xml_path)
    except (OSError, AsteriskCliError) as err:
        msg = f"File system error during phone deprovisioning: {err}"
        raise AsteriskServiceError(msg) from err

    log.info(
        "Successfully deprovisioned phone (Extension: %s, MAC: %s)",
        extension,
        mac_address,
    )


def _cleanup_created_files(created_files: Iterable[Path]) -> None:
    """Remove files created during a failed provisioning attempt.

    Args:
        created_files: Paths of files to delete if they exist.
    """
    for file_path in created_files:
        if file_path.exists():
            try:
                file_path.unlink()
                log.info("Removed orphaned file: %s", file_path)
            except OSError as e:
                log.error(
                    "Failed to remove orphaned file '%s': %s", file_path, e
                )


def _write_provisioning_files(
    phone: Phone,
    voicemail: Voicemail | None,
    created_files: list[Path],
) -> None:
    """Write provisioning entries to sip.conf, extensions.conf, voicemail.conf.

    Args:
        phone: Target Phone dataclass.
        voicemail: Optional Voicemail configuration.
        created_files: Tracking list for generated files, appended to as
            new files are created.
    """
    cnf_path = TFTPBOOT / (
        f"{SEP_PREFIX}{phone.mac_address}{XML_CONFIG_EXTENSION}"
    )
    _generate_cnf_xml(extension=phone.extension, mac_address=phone.mac_address)
    created_files.append(cnf_path)

    sip_content: str = (
        f"\n[{SEP_PREFIX}{phone.mac_address}](phone)\n"
        f"authname={SEP_PREFIX}{phone.mac_address}\n"
        f"secret={SEP_PREFIX}{phone.mac_address}\n"
        f"callerid={phone.caller_id}\n"
    )

    if voicemail:
        sip_content += f"mailbox={phone.extension}@{MAILBOX_CONTEXT}\n"

    sip_content += "\n"

    _patch_file(SIP_CONF, sip_content)

    _patch_file(
        EXTENSIONS_CONF,
        f"exten => {phone.extension}"
        f",1,Dial(SIP/{SEP_PREFIX}{phone.mac_address},14,t)\n",
    )

    if voicemail:
        _patch_file(
            EXTENSIONS_CONF,
            f"exten => {phone.extension},n,Voicemail({phone.extension},u)\n",
        )
        _patch_file(
            VOICEMAIL_CONF,
            f"{phone.extension} = {phone.extension}, {voicemail.name}, "
            f"{voicemail.email},,attach=yes|delete=1\n",
        )


def _provision_phone(
    phone: Phone,
    voicemail: Voicemail | None,
) -> None:
    """Provision phone configuration files and catch IO exceptions.

    Args:
        phone: Phone dataclass.
        voicemail: Optional Voicemail dataclass.

    Raises:
        AsteriskServiceError: If any part of provisioning fails. The
            three config files are rolled back to their prior state,
            and any newly created .cnf.xml file is removed, before this
            is raised.
    """
    created_files: list[Path] = []

    try:
        with ConfigTransaction((SIP_CONF, EXTENSIONS_CONF, VOICEMAIL_CONF)):
            _write_provisioning_files(phone, voicemail, created_files)
    except (OSError, AsteriskCliError) as err:
        _cleanup_created_files(created_files)
        msg = f"File system error during registration: {err}"
        raise AsteriskServiceError(msg) from err


def _replace_mac_in_file(file_path: Path, old_mac: str, new_mac: str) -> None:
    """Replace all occurrences of a MAC address in a specified config file.

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

    file_path.write_text(data=updated_content, encoding="utf-8")
    log.info("Updated %s", file_path.name)


def _generate_cnf_xml(extension: str, mac_address: str) -> None:
    """Create a new .cnf.xml file from the template with values patched in.

    Args:
        extension: The extension of the new phone.
        mac_address: The MAC address of the new phone.
    """
    new_cnf_xml: Path = TFTPBOOT / (
        f"{SEP_PREFIX}{mac_address}{XML_CONFIG_EXTENSION}"
    )

    copy_file_safe(src=XML_TEMPLATE, dst=new_cnf_xml)

    _patch_cnf_xml(
        file_path=new_cnf_xml,
        placeholder="--EXTENNUMBER--",
        new_value=extension,
    )
    log.debug(
        "Patched extension '%s' into new .cnf.xml file '%s'.",
        extension,
        new_cnf_xml,
    )

    _patch_cnf_xml(
        file_path=new_cnf_xml,
        placeholder="--SEPMAC--",
        new_value=f"{SEP_PREFIX}{mac_address}",
    )
    log.debug(
        "Patched MAC address '%s' into new .cnf.xml file '%s'.",
        mac_address,
        new_cnf_xml,
    )

    log.info("Successfully created and patched '%s'", new_cnf_xml)


def _patch_file(file_path: Path, content: str) -> None:
    """Append a given string to a config file.

    Args:
        file_path: Path of file to modify.
        content: String content to append.
    """
    with file_path.open(mode="a", encoding="utf-8") as file:
        file.write(content)
    log.debug("Appended '%s' to '%s'", content, file_path)


def register_phone(phone: Phone, voicemail: Voicemail | None = None) -> None:
    """Orchestrate interactive phone registration workflow.

    Args:
        phone: The extension, MAC address, and caller ID to register.
        voicemail: Optional voicemail configuration for the phone.
    """
    if search_for_extension(phone.extension):
        log.error("Extension '%s' is already in use!", phone.extension)
        return

    if search_for_mac_address(phone.mac_address):
        log.error("MAC address '%s' is already in use!", phone.mac_address)
        return

    print_phone_table(phone, voicemail)

    should_continue: bool | None = None
    while should_continue is None:
        should_continue = questionary.confirm(
            message="Are you sure you wish to register this phone?",
            default=True,
        ).ask()

    if not should_continue:
        log.error("User cancelled interaction.")
        return

    _provision_phone(phone, voicemail)


def remove_phone(search_method: str, search_key: str) -> None:
    """Prompt user to search for and delete an existing phone configuration.

    Args:
        search_method: Method to search ('ext' or 'mac').
        search_key: Search string value.

    Raises:
        AsteriskCliError: If search_method is neither 'ext' nor 'mac',
            or if a MAC/extension cannot be resolved from the search.
    """
    extension: str = ""
    mac_address: str = ""
    found: list[ConfigMatch] = []

    if search_method == SEARCH_BY_EXTENSION:
        extension = search_key
        found = search_for_extension(extension)
        if not found:
            msg = f"Could not find phone with extension {extension}."
            raise AsteriskCliError(msg)
        mac_address = get_mac_from_ext(matches=found)
        caller_id = get_caller_id_from_ext(matches=found)
    elif search_method == SEARCH_BY_MAC:
        mac_address = search_key
        found = search_for_mac_address(mac_address)
        if not found:
            msg = f"Could not find phone with MAC address '{mac_address}'."
            raise AsteriskCliError(msg)
        extension = get_ext_from_mac(matches=found)
        caller_id = get_caller_id_from_ext(
            matches=search_for_extension(extension)
        )
    else:
        msg = f"Invalid search method: {search_method}"
        log.error(msg)
        raise AsteriskCliError(msg)

    phone_model = Phone(
        extension=extension, mac_address=mac_address, caller_id=caller_id
    )
    print_phone_table(phone_model)

    should_continue: bool = questionary.confirm(
        message="Are you sure you wish to delete/deregister this phone?",
        default=False,
    ).ask()

    if not should_continue:
        log.error("User cancelled interaction.")
        return

    _deprovision_phone(extension, mac_address)


def replace_phone(search_method: str, search_key: str) -> None:
    """Replace a phone MAC address.

    Args:
        search_method: Method to search ('ext' or 'mac').
        search_key: Search string value.

    Raises:
        AsteriskCliError: If no valid search option was selected.
        AsteriskServiceError: If the new MAC address is already
            registered, or if the update fails. sip.conf and
            extensions.conf are rolled back to their prior state before
            this is raised.
    """
    extension: str = ""
    mac_address: str = ""

    if search_method == SEARCH_BY_EXTENSION:
        extension = search_key
        extension_matches: list[ConfigMatch] = search_for_extension(extension)
        mac_address = get_mac_from_ext(extension_matches)
    elif search_method == SEARCH_BY_MAC:
        mac_address = search_key
        mac_matches: list[ConfigMatch] = search_for_mac_address(mac_address)
        extension = get_ext_from_mac(mac_matches)
    else:
        msg = "No option selected."
        log.error(msg)
        raise AsteriskCliError(msg)

    old_cnf_file: Path = TFTPBOOT / (
        f"{SEP_PREFIX}{mac_address}{XML_CONFIG_EXTENSION}"
    )
    if old_cnf_file.exists():
        old_cnf_file.unlink()
        log.info("Deleted old .cnf.xml file for SEP%s.", mac_address)
    else:
        log.warning("No old .cnf.xml file found for SEP%s.", mac_address)

    new_mac_address: str = read_mac_addr()
    existing_macs: list[ConfigMatch] = search_for_mac_address(new_mac_address)
    if existing_macs:
        msg = f"Phone with MAC address {new_mac_address} already exists."
        log.error(msg)
        raise AsteriskServiceError(msg)

    _generate_cnf_xml(extension=extension, mac_address=new_mac_address)

    try:
        with ConfigTransaction((SIP_CONF, EXTENSIONS_CONF)):
            for config_file in (SIP_CONF, EXTENSIONS_CONF):
                _replace_mac_in_file(
                    file_path=config_file,
                    old_mac=mac_address,
                    new_mac=new_mac_address,
                )
    except OSError as err:
        msg = f"File system error while replacing MAC address: {err}"
        raise AsteriskServiceError(msg) from err

    log.info("Updated sip.conf and extensions.conf with new MAC address.")
    log.info("Operation completed.")
