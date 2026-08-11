"""Registers a CISCO Phone in the Asterisk PBX phone system."""

import shutil
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import questionary
from rich.table import Table

from cli import (
    read_caller_id,
    read_email,
    read_extension,
    read_mac_addr,
    read_name,
)
from config import REQUIRED_FILES, TFTPBOOT, console, log
from search_for_extension import search_for_extension
from search_for_mac_address import search_for_mac_address


@dataclass
class Phone:
    """Information for phone registration.

    Attributes:
        extension: The 4-digit extension for the new phone.
        mac_address: The MAC address for the new phone.
        caller_id: The caller ID, if any, for the new phone.
    """

    extension: str
    mac_address: str
    caller_id: str


@dataclass
class Voicemail:
    """Information for voicemail.

    Attributes:
        name: Name of the person to send voicemails to.
        email: Email address of the person to send voicemails to.
    """

    name: str
    email: str


def safe_exit(
    created_files: Iterable[Path] | None = None,
    backups: dict[Path, Path] | None = None,
    exit_code: int = 1,
) -> None:
    """Reverts all changes and exits the script.

    Args:
        created_files: Paths of new files created during execution to delete.
        backups: Mapping of original file paths to backup filepaths to restore.
        exit_code: System exit code to return.
    """
    log.warning("Initiating safe exit. Reverting changes...")

    if created_files:
        for file_path in created_files:
            if file_path.exists():
                try:
                    file_path.unlink()
                    log.info("Removed created file: %s", file_path)
                except OSError as e:
                    log.error("Failed to remove '%s': %s", file_path, e)

    if backups:
        for original_path, backup_path in backups.items():
            if backup_path.exists():
                try:
                    shutil.copyfile(src=backup_path, dst=original_path)
                    log.info(
                        "Restored '%s' from '%s'", original_path, backup_path
                    )
                except OSError as e:
                    log.error("Failed to restore '%s': %s", original_path, e)

    sys.exit(exit_code)


def print_phone_information(
    phone: Phone, voicemail: Voicemail | None = None
) -> None:
    """Print the information for a new phone in a Rich table."""
    table = Table(title="Phone Information")

    table.add_column(header="Extension")
    table.add_column(header="MAC Address")
    row_values: list[str] = [phone.extension, phone.mac_address]

    if phone.caller_id:
        table.add_column(header="Caller ID")
        row_values.append(phone.caller_id)

    if voicemail:
        table.add_column(header="Voicemail Name")
        table.add_column(header="Voicemail Email")
        row_values.extend([voicemail.name, voicemail.email])

    table.add_row(*row_values)

    console.print(table)


def _copy_file_safe(src: Path, dst: Path) -> None:
    try:
        shutil.copyfile(src=src, dst=dst)
    except FileNotFoundError:
        log.error(
            "Source file (%s) does not exist or "
            + "target directory (%s) is missing.",
            src,
            TFTPBOOT,
        )
    except shutil.SameFileError:
        log.error("Source and destination paths point to the same file.")
        return
    except PermissionError:
        log.error("Permission denied accessing source or destination.")
        return
    except OSError as e:
        log.error("System error during file copy: %s", e)
        return
    log.debug("Copied '%s' to '%s'", src, dst)


def _patch_cnf_xml(file_path: Path, placeholder: str, new_value: str) -> None:
    content: str = file_path.read_text(encoding="utf-8")
    updated_content: str = content.replace(placeholder, new_value)
    file_path.write_text(data=updated_content, encoding="utf-8")


def generate_cnf_xml(extension: str, mac_address: str) -> None:
    """Creates new .cnf.xml file from template with values patched in.

    Replaces --SEPMAC-- with the mac address
        and --EXTENNUMBER-- with the extension.

    Args:
        extension: The extension of the new phone.
        mac_address: The MAC address of the new phone.
    """
    cnf_xml_template: Path = REQUIRED_FILES["XML_TEMPLATE"]
    new_cnf_xml: Path = TFTPBOOT / f"SEP{mac_address}.cnf.xml"

    _copy_file_safe(src=cnf_xml_template, dst=new_cnf_xml)

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
        file_path=new_cnf_xml, placeholder="--SEPMAC--", new_value=mac_address
    )
    log.debug(
        "Patched MAC address '%s' into new .cnf.xml file '%s'.",
        mac_address,
        new_cnf_xml,
    )

    log.info("Successfully created and patched '%s'", new_cnf_xml)


def _backup_config_file(src_config: Path) -> Path:
    backup_dir: Path = src_config.parent / "backup"
    timestamp: str = datetime.now(tz=ZoneInfo("America/New_York")).strftime(
        "%Y-%m-%d_%H:%M:%S"
    )
    if not backup_dir.exists():
        log.error("Backup directory does not exist!")
        raise FileNotFoundError(backup_dir)
    backup_path: Path = backup_dir / Path(f"{src_config}_{timestamp}")
    _copy_file_safe(src=src_config, dst=backup_path)
    log.debug("Backed up '%s'", src_config)
    return backup_path


def patch_file(file_path: Path, content: str) -> None:
    """Appends a given string to a config file.

    Args:
        file_path: Path of file to modify.
        content: String content to append.
    """
    with file_path.open(mode="a", encoding="utf=8") as file:
        file.write(content)
    log.debug("Appended '%s' to '%s'", content, file_path)


def _write_provisioning_files(
    phone: Phone,
    voicemail: Voicemail | None,
    created_files: list[Path],
    backups: dict[Path, Path],
) -> None:
    ext_conf = REQUIRED_FILES["EXTENSIONS_CONF"]
    sip_conf: Path = REQUIRED_FILES["SIP_CONF"]

    cnf_path = TFTPBOOT / f"SEP{phone.mac_address}.cnf.xml"
    generate_cnf_xml(extension=phone.extension, mac_address=phone.mac_address)
    created_files.append(cnf_path)

    backups[sip_conf] = _backup_config_file(sip_conf)
    patch_file(
        sip_conf,
        f"\n[SEP{phone.mac_address}](phone)\n"
        f"authname=SEP{phone.mac_address}\n"
        f"secret=SEP{phone.mac_address}\n"
        f"caller_id={phone.caller_id}\n\n",
    )

    backups[ext_conf] = _backup_config_file(ext_conf)
    patch_file(
        ext_conf,
        f"exten => {phone.extension}"
        f",1,Dial(SIP/SEP{phone.mac_address},14,t)\n",
    )

    if voicemail:
        patch_file(
            ext_conf,
            f"exten => {phone.extension},n,Voicemail({phone.extension},u)\n",
        )


def _provision_phone(
    phone: Phone,
    voicemail: Voicemail | None,
) -> None:
    created_files: list[Path] = []
    backups: dict[Path, Path] = {}

    try:
        _write_provisioning_files(phone, voicemail, created_files, backups)
    except OSError as err:
        log.error("File system error during phone registration: %s", err)
        safe_exit(created_files=created_files, backups=backups)


def register_phone() -> None:
    """Main orchestrator."""
    extension: str = read_extension()
    if search_for_extension(extension):
        log.error("Extension '%s' is already in use!", extension)
        return

    mac_address: str = read_mac_addr()
    if search_for_mac_address(mac_address):
        log.error("MAC address '%s' is already in use!", mac_address)
        return

    phone: Phone = Phone(
        extension=extension,
        mac_address=mac_address,
        caller_id=read_caller_id(extension),
    )

    use_voicemail: bool | None = None
    while use_voicemail is None:
        use_voicemail = questionary.confirm(
            message="Will this phone have need voicemail?", default=False
        ).ask()

    voicemail = (
        Voicemail(name=read_name(), email=read_email())
        if use_voicemail
        else None
    )

    print_phone_information(phone, voicemail)

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


if __name__ == "__main__":
    register_phone()
