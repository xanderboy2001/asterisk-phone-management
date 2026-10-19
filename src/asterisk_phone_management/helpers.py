"""Helper functions."""

import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from asterisk_phone_management.core.constants import (
    CALLERID_DIRECTIVE,
    EXTENSIONS_CONF,
    EXTENSIONS_CONF_NAME,
    SEP_PREFIX,
    SIP_CONF_NAME,
    TFTPBOOT,
    CallForwardingDefinition,
    log,
)
from asterisk_phone_management.core.exceptions import AsteriskCliError
from asterisk_phone_management.schemas.models import ConfigMatch
from asterisk_phone_management.services.search import search_for_extension


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
        AsteriskCliError: If permissions error occurs when
            creating backup directory.
    """
    backup_dir: Path = src_config.parent / "backup"
    timestamp: str = datetime.now(tz=ZoneInfo("America/New_York")).strftime(
        "%Y-%m-%d_%H:%M:%S"
    )
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        msg = f"Permission denied creating backup directory: {backup_dir}"
        log.error(msg)
        raise AsteriskCliError(msg) from e

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
        if match.file_path.name == EXTENSIONS_CONF_NAME:
            mac_match = re.search(
                pattern=r"SIP/SEP([A-Fa-f0-9]{12})", string=match.matched_text
            )
            if mac_match:
                return str(mac_match.group(1).upper())
        elif match.file_path.name == SIP_CONF_NAME:
            mac_match = re.search(
                pattern=r"SEP([A-Fa-f0-9]{12})", string=match.matched_text
            )
            if mac_match:
                return str(mac_match.group(1).upper())
        elif match.file_path.suffixes == [".cnf", ".xml"]:
            xml_root = ET.parse(match.file_path).getroot()
            name_element = xml_root.find(".//name")
            name_text = (
                (name_element.text or "") if name_element is not None else ""
            )
            if name_text:
                return name_text.upper().removeprefix(SEP_PREFIX)

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
            extension_text = (
                (extension_element.text or "")
                if extension_element is not None
                else ""
            )
            if extension_text:
                return extension_text
        elif match.file_path.name == EXTENSIONS_CONF_NAME:
            ext_match = re.search(
                pattern=r"exten\s*=>\s*(\d{4})", string=match.matched_text
            )
            if ext_match:
                return str(ext_match.group(1))

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
            match.file_path.name == SIP_CONF_NAME
            and match.matched_text.startswith(CALLERID_DIRECTIVE)
        ):
            return match.matched_text.removeprefix(CALLERID_DIRECTIVE)

    msg = "Could not determine caller ID from extension number!"
    log.error(msg)
    raise AsteriskCliError(msg)


def get_call_forwarding_config(user: CallForwardingDefinition) -> ConfigMatch:
    """Find the user's forwarding line in ``extensions.conf``.

    Args:
        user: The user whose extension should be located.

    Returns:
        The single config match for the user's extension.

    Raises:
        AsteriskCliError: If no match, or more than one match, is found.
    """
    extension_matches: list[ConfigMatch] = [
        match
        for match in search_for_extension(user.extension)
        if match.file_path == EXTENSIONS_CONF
        and user.forwarding_number in match.matched_text
    ]

    if not extension_matches:
        msg = f"Could not find any matches for {user.name}."
        log.error(msg)
        raise AsteriskCliError(msg)

    if len(extension_matches) > 1:
        err_msg = (
            f"Multiple matches found for {user.name}. "
            "I don't know which one to edit!"
        )
        log.error(err_msg)
        for match in extension_matches:
            msg = (
                f"File: {match.file_path} ({match.line_number}): "
                f"'{match.matched_text}'"
            )
            log.error(msg)
        raise AsteriskCliError(err_msg)

    return extension_matches[0]
