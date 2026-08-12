"""Helper functions."""

import re
import shutil
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import TFTPBOOT, log
from search_for_extension import ExtensionMatch
from search_for_mac_address import MACMatch


def copy_file_safe(src: Path, dst: Path) -> None:
    """Copies a file with extra guards.

    Args:
        src: Source file to copy.
        dst: Destination to copy to.
    """
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


def backup_config_file(src_config: Path) -> Path:
    """Backs up a config file with an appended timestamp.

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


def get_mac_from_ext(matches: list[ExtensionMatch]) -> str:
    """Determines the MAC address from a list of extension matches.

    Args:
        matches: List of ExtensionMatch objects.

    Returns:
        The MAC address string in uppercase.

    Raises:
        SystemExit: If no MAC address can be determined.
    """
    for match in matches:
        if match.file_path.name == "extensions.conf":
            mac_match = re.search(
                pattern=r"SIP/SEP([A-Fa-f0-9]{12})", string=match.matched_text
            )
            if mac_match:
                return mac_match.group(1).upper()
        elif match.file_path.name == "sip.conf":
            mac_match = re.search(f"SEP([A-Fa-f0-9]{12})", match.matched_text)
            if mac_match:
                return mac_match.group(1).upper()
        elif match.file_path.suffixes == [".cnf", ".xml"]:
            xml_root = ET.parse(match.file_path).getroot()
            name_element = xml_root.find(".//name")
            if name_element is not None and name_element.text:
                return name_element.text.upper()

    log.error("Could not determine MAC address from extension number!")
    raise SystemExit(1)


def get_ext_from_mac(matches: list[MACMatch]) -> str:
    """Determine the extension from a list of MAC matches.

    Args:
        matches: List of MACMatch objects.

    Returns:
        The extension as a string.

    Raises:
        SystemExit: If no extension can be determined.
    """
    for match in matches:
        if match.file_path.suffixes == [".cnf", ".xml"]:
            xml_root: ET.Element = ET.parse(match.file_path).getroot()
            extension_element: ET.Element[str] | None = xml_root.find(
                path=".//featureLabel"
            )
            if extension_element is not None and extension_element.text:
                return extension_element.text
        elif match.file_path.name == "extensions.conf":
            ext_match = re.search(r"exten\s*=>\s*(\d{4})", match.matched_text)
            if ext_match:
                return ext_match.group(1)

    log.error("Could not determine extension from MAC address!")
    raise SystemExit(1)
