"""Helper functions."""

import shutil
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import TFTPBOOT, log


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
