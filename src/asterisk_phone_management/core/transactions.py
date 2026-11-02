"""Transactional context manager for Asterisk configuration files."""

import fcntl
import os
import shutil
import time
from collections.abc import Iterable
from pathlib import Path
from types import TracebackType
from typing import Self

from asterisk_phone_management.core.constants import LOCK_FILE, log
from asterisk_phone_management.core.exceptions import FileTransactionError
from asterisk_phone_management.helpers import backup_config_file

# How often to retry while another process holds the lock.
_LOCK_POLL_SECONDS: float = 0.1


class ConfigTransaction:
    """Context manager for safely editing Asterisk config files with rollback.

    Automatically creates backups upon entry and rolls back changes if an
    exception is raised within the context. Exceptions are never swallowed:
    after rollback, the original exception continues to propagate so the
    caller (or the CLI's top-level handler) can react to it.

    Only one transaction can run at a time across all processes: each one
    holds an exclusive lock on ``LOCK_FILE`` from entry to exit. Don't nest
    transactions; the inner one would wait for the outer one's lock and
    time out. The lock uses ``fcntl``, so this module is Unix-only.
    """

    def __init__(
        self, target_files: Iterable[Path], lock_timeout: float = 10.0
    ) -> None:
        """Initialize the transaction with files to protect.

        Args:
            target_files: An iterable of file paths to backup and manage.
            lock_timeout: Seconds to wait for another change to finish
                before giving up. Defaults to 10.
        """
        self.target_files: Iterable[Path] = target_files
        self.lock_timeout: float = lock_timeout
        self.backups: dict[Path, Path] = {}
        self._lock_fd: int | None = None

    def __enter__(self) -> Self:
        """Take the lock, then back up every target file.

        Returns:
            This transaction instance.

        Raises:
            FileTransactionError: If another change holds the lock past the
                timeout, the lock file can't be opened, or any file could
                not be backed up.
        """
        self._acquire_lock()
        try:
            self._backup_all()
        except BaseException:
            self._release_lock()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Roll back if the block raised, then always release the lock.

        Args:
            exc_type: The exception type raised in the block, if any.
            exc_val: The exception instance raised in the block, if any.
            exc_tb: The traceback for the raised exception, if any.

        Returns:
            False in all cases, so any exception continues to propagate.
        """
        try:
            if exc_type is not None:
                log.warning(
                    "Exception during file operations. Rolling back..."
                )
                self._rollback()
        finally:
            self._release_lock()
        return False

    def _backup_all(self) -> None:
        """Back up every target file, rolling back any already copied.

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

    def _acquire_lock(self) -> None:
        """Take the exclusive config lock, retrying until the timeout.

        Raises:
            FileTransactionError: If the lock file can't be opened, or the
                lock is still held by someone else when the timeout passes.
        """
        try:
            fd = os.open(LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o600)
        except OSError as e:
            msg = f"Cannot open lock file {LOCK_FILE}: {e}"
            log.error(msg)
            raise FileTransactionError(msg) from e

        deadline = time.monotonic() + self.lock_timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    os.close(fd)
                    msg = (
                        "Another change is in progress. Try again in a moment."
                    )
                    log.error(msg)
                    raise FileTransactionError(msg) from None
                time.sleep(_LOCK_POLL_SECONDS)
            else:
                self._lock_fd = fd
                return

    def _release_lock(self) -> None:
        """Release the config lock if this transaction holds it."""
        if self._lock_fd is None:
            return
        fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
        os.close(self._lock_fd)
        self._lock_fd = None

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
