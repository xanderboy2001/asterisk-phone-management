"""Transactional context manager for Asterisk configuration files."""

import shutil
from collections.abc import Iterable
from pathlib import Path
from types import TracebackType
from typing import Self

from asterisk_phone_management.core.constants import log
from asterisk_phone_management.core.exceptions import FileTransactionError
from asterisk_phone_management.helpers import backup_config_file


class ConfigTransaction:
    """Context manager for safely editing Asterisk config files with rollback.

    Automatically creates backups upon entry and rolls back changes if an
    exception is raised within the context. Exceptions are never swallowed:
    after rollback, the original exception continues to propagate so the
    caller (or the CLI's top-level handler) can react to it.
    """

    def __init__(self, target_files: Iterable[Path]) -> None:
        """Initialize the transaction with files to protect.

        Args:
            target_files: An iterable of file paths to backup and manage.
        """
        self.target_files: Iterable[Path] = target_files
        self.backups: dict[Path, Path] = {}

    def __enter__(self) -> Self:
        """Back up every target file before the caller edits them.

        Returns:
            This transaction instance.

        Raises:
            FileTransactionError: If any file could not be backed up.
        """
        for file_path in self.target_files:
            try:
                self.backups[file_path] = backup_config_file(file_path)
            except (OSError, Exception) as e:
                log.error("Failed to backup %s: %s", file_path, e)
                self._rollback()
                msg = f"Backup failed for {file_path}"
                raise FileTransactionError(msg) from e
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Roll back all tracked files if the block raised an exception.

        Args:
            exc_type: The exception type raised in the block, if any.
            exc_val: The exception instance raised in the block, if any.
            exc_tb: The traceback for the raised exception, if any.

        Returns:
            False in all cases, so any exception continues to propagate.
        """
        if exc_type is not None:
            log.warning(
                "Exception detected during file operations. Rolling back..."
            )
            self._rollback()
        return False

    def _rollback(self) -> None:
        """Restore original files from their created backups."""
        for original, backup in self.backups.items():
            if backup.exists():
                try:
                    shutil.copyfile(backup, original)
                    log.info("Rolled back %s", original.name)
                except OSError as e:
                    log.error(
                        "CRITICAL: Failed to rollback %s: %s", original.name, e
                    )
