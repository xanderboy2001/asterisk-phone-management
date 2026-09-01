"""Helper functions."""

import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from asterisk_phone_management.core.constants import TFTPBOOT, log
from asterisk_phone_management.core.exceptions import AsteriskCliError
from asterisk_phone_management.schemas.models import ConfigMatch


def copy_file_safe(src: Path, dst: Path) -> None:
    """Copy a file with extra guards.

    Args:
        src: Source file to copy.
        dst: Destination to copy to.

    Raises:
        AsteriskCliError: If the copy fails for any filesystem-related reason
            (missing source, same-file, permissions, or other OS errors).
    """
    try:
        shutil.copyfile(src=src, dst=dst)
    except FileNotFoundError as e:
        msg = (
            f"Source file ({src}) does not exist or "
            f"target directory ({TFTPBOOT}) is missing."
        )
        log.error(msg)
        raise AsteriskCliError(msg) from e
    except shutil.SameFileError as e:
        msg = "Source and destination paths point to the same file."
        log.error(msg)
        raise AsteriskCliError(msg) from e
    except PermissionError as e:
        msg = "Permission denied accessing source or destination."
        log.error(msg)
        raise AsteriskCliError(msg) from e
    except OSError as e:
        msg = f"System error during file copy: {e}"
        log.error(msg)
        raise AsteriskCliError(msg) from e
    log.debug("Copied '%s' to '%s'", src, dst)


def backup_config_file(src_config: Path) -> Path:
    """Back up a config file with an appended timestamp.

    Args:
        src_config: The config to backup.

    Returns:
        The path to the newly created backup.

    Raises:
        FileNotFoundError: If the provided config file was not found.
    """
    backup_dir: Path = src_config.parent / "backup"
    timestamp: str = datetime.now(tz=ZoneInfo("America/New_York")).strftime(
        "%Y-%m-%d_%H:%M:%S"
    )
    if not backup_dir.exists():
        log.error("Backup directory does not exist!")
        raise FileNotFoundError(backup_dir)
    backup_path: Path = backup_dir / Path(f"{src_config.name}_{timestamp}")
    copy_file_safe(src=src_config, dst=backup_path)
    log.debug("Backed up '%s'", src_config)
    return backup_path


def get_mac_from_ext(matches: list[ConfigMatch]) -> str:
    """Determine the MAC address from a list of extension matches.

    Args:
        matches: List of ConfigMatch objects.

    Returns:
        The MAC address string in uppercase.

    Raises:
        AsteriskCliError: If no MAC address can be determined.
    """
    for match in matches:
        if match.file_path.name == "extensions.conf":
            mac_match = re.search(
                pattern=r"SIP/SEP([A-Fa-f0-9]{12})", string=match.matched_text
            )
            if mac_match:
                return mac_match.group(1).upper()
        elif match.file_path.name == "sip.conf":
            mac_match = re.search(
                pattern=r"SEP([A-Fa-f0-9]{12})", string=match.matched_text
            )
            if mac_match:
                return mac_match.group(1).upper()
        elif match.file_path.suffixes == [".cnf", ".xml"]:
            xml_root = ET.parse(match.file_path).getroot()
            name_element = xml_root.find(".//name")
            if name_element is not None and name_element.text:
                return name_element.text.upper().removeprefix("SEP")

    msg = "Could not determine MAC address from extension number!"
    log.error(msg)
    raise AsteriskCliError(msg)


def get_ext_from_mac(matches: list[ConfigMatch]) -> str:
    """Determine the extension from a list of MAC matches.

    Args:
        matches: List of ConfigMatch objects.

    Returns:
        The extension as a string.

    Raises:
        AsteriskCliError: If no extension can be determined.
    """
    for match in matches:
        if match.file_path.suffixes == [".cnf", ".xml"]:
            xml_root: ET.Element = ET.parse(match.file_path).getroot()
            extension_element: ET.Element | None = xml_root.find(
                path=".//featureLabel"
            )
            if extension_element is not None and extension_element.text:
                return extension_element.text
        elif match.file_path.name == "extensions.conf":
            ext_match = re.search(
                pattern=r"exten\s*=>\s*(\d{4})", string=match.matched_text
            )
            if ext_match:
                return ext_match.group(1)

    msg = "Could not determine extension from MAC address!"
    log.error(msg)
    raise AsteriskCliError(msg)


def get_caller_id_from_ext(matches: list[ConfigMatch]) -> str:
    """Determine the caller ID string from a list of extension matches.

    Args:
        matches: List of ConfigMatch objects.

    Returns:
        The caller ID string extracted from sip.conf.

    Raises:
        AsteriskCliError: If caller ID directive cannot be found.
    """
    for match in matches:
        if (
            match.file_path.name == "sip.conf"
            and match.matched_text.startswith("callerid=")
        ):
            return match.matched_text.removeprefix("callerid=")

    msg = "Could not determine caller ID from extension number!"
    log.error(msg)
    raise AsteriskCliError(msg)
