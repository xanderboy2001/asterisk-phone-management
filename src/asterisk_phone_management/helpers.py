"""Helper functions."""

import os
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from asterisk_phone_management.core.constants import (
    CALLERID_DIRECTIVE,
    EXTENSIONS_CONF_NAME,
    SEP_PREFIX,
    SIP_CONF_NAME,
    CallForwardingDefinition,
    log,
)
from asterisk_phone_management.core.exceptions import AsteriskCliError
from asterisk_phone_management.core.settings import get_settings
from asterisk_phone_management.schemas.models import ConfigMatch
from asterisk_phone_management.services.search import search_for_extension


def _fill_temp_file(fd: int, tmp: Path, target: Path, data: bytes) -> None:
    """Write data to a temp file and match the target's mode and owner.

    Args:
        fd: Open file descriptor for the temp file; closed on return.
        tmp: Path of the temp file.
        target: The file the temp file will replace.
        data: The complete new contents.
    """
    # Write the data and force it to disk.
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    # Copy the original file's permissions and owner so Asterisk can
    # still read it.
    shutil.copymode(target, tmp)
    st = target.stat()
    os.chown(tmp, st.st_uid, st.st_gid)


def atomic_write_text(path: Path, data: str) -> None:
    """Replace a file's contents with UTF-8 text, atomically.

    See ``atomic_write_bytes`` for how the replacement works.

    Args:
        path: The file to replace.
        data: The complete new contents.
    """
    atomic_write_bytes(path, data.encode("utf-8"))


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Replace a file's contents so readers never see a partial write.

    The new contents are written to a temporary file in the same
    directory, then renamed over the original in one step. If anything
    fails, the temporary file is removed and the original is untouched.

    Args:
        path: The file to replace.
        data: The complete new contents.
    """
    # Follow symlinks, so we replace the real file, not the link.
    target: Path = path.resolve()
    # Same directory = same filesystem, so the rename is atomic.
    fd, tmp_name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
    )
    tmp = Path(tmp_name)
    try:
        _fill_temp_file(fd, tmp, target, data)
        tmp.replace(target)
    except BaseException:
        # Includes Ctrl+C; always re-raised after cleanup.
        tmp.unlink(missing_ok=True)
        raise


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
            f"target directory ({dst.parent}) is missing."
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


# Backups hold SIP secrets and voicemail PINs, so only the owner may read
# them, whatever the process umask.
_BACKUP_DIR_MODE: int = 0o700
_BACKUP_FILE_MODE: int = 0o600


def _write_private_copy(src: Path, dst: Path) -> None:
    """Copy a file to a new file that only its owner can read.

    The destination is created with mode 0600 in the same call that opens
    it, so it is never readable by others, even briefly. It must not
    already exist.

    Args:
        src: The file to copy.
        dst: The new file to create.

    Raises:
        AsteriskCliError: If the source can't be read, the destination
            already exists, or the copy fails.
    """
    try:
        with src.open("rb") as source:
            fd = os.open(
                dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _BACKUP_FILE_MODE
            )
            with os.fdopen(fd, "wb") as target:
                shutil.copyfileobj(source, target)
    except FileNotFoundError as e:
        msg = f"Cannot back up {src}: file not found."
        log.error(msg)
        raise AsteriskCliError(msg) from e
    except FileExistsError as e:
        msg = f"Backup {dst} already exists; not overwriting it."
        log.error(msg)
        raise AsteriskCliError(msg) from e
    except OSError as e:
        dst.unlink(missing_ok=True)
        msg = f"Failed to back up {src}: {e}"
        log.error(msg)
        raise AsteriskCliError(msg) from e


def backup_config_file(src_config: Path) -> Path:
    """Back up a config file with an appended timestamp.

    The backup directory is restricted to its owner (0700) and each backup
    is created owner-only (0600), because the files contain SIP secrets
    and voicemail PINs. An existing, more open backup directory is
    tightened, which also protects backups made before this change.

    Args:
        src_config: The config to backup.

    Returns:
        The path to the newly created backup.

    Raises:
        AsteriskCliError: If the backup directory can't be created or
            restricted, or the backup can't be written.
    """
    backup_dir: Path = src_config.parent / "backup"
    # Microseconds keep two backups made in the same second from clashing.
    timestamp: str = (
        datetime.now().astimezone().strftime("%Y-%m-%d_%H:%M:%S.%f")
    )
    try:
        backup_dir.mkdir(mode=_BACKUP_DIR_MODE, parents=True, exist_ok=True)
        backup_dir.chmod(_BACKUP_DIR_MODE)
    except PermissionError as e:
        msg = f"Permission denied creating backup directory: {backup_dir}"
        log.error(msg)
        raise AsteriskCliError(msg) from e

    backup_path: Path = backup_dir / f"{src_config.name}_{timestamp}"
    _write_private_copy(src_config, backup_path)
    log.debug("Backed up '%s'", src_config)
    return backup_path


def _parse_xml(file_path: Path) -> ET.Element:
    try:
        return ET.parse(file_path).getroot()
    except (ET.ParseError, OSError) as e:
        msg = f"Could not read phone config {file_path.name}: {e}"
        log.error(msg)
        raise AsteriskCliError(msg) from e


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
            xml_root = _parse_xml(match.file_path)
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
            xml_root: ET.Element = _parse_xml(match.file_path)
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
                pattern=r"exten\s*=>\s*(\d{4})\s*,", string=match.matched_text
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
        if match.file_path == get_settings().extensions_conf
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
