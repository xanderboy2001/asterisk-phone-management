"""Unit tests for transactional config file backups and rollback context manager."""

import fcntl
import os
import threading
from collections.abc import Generator
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management.core import transactions
from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    FileTransactionError,
)
from asterisk_phone_management.core.transactions import ConfigTransaction


def _corrupt_then_fail(path: Path) -> None:
    """Write bad content inside a transaction, then raise to force a rollback.

    Args:
        path: The config file protected by the transaction.

    Raises:
        RuntimeError: Always, to trigger the rollback.
    """
    with ConfigTransaction((path,)):
        path.write_text("corrupted content", encoding="utf-8")
        err_msg = "Simulated error"
        raise RuntimeError(err_msg)


def _fail_with_broken_rollback(path: Path, mocker: MockerFixture) -> None:
    """Raise inside a transaction after making the rollback copy fail.

    Args:
        path: The config file protected by the transaction.
        mocker: The pytest-mock fixture used to break the rollback.

    Raises:
        RuntimeError: Always, to trigger the rollback.
    """
    with ConfigTransaction((path,)):
        # Patch after __enter__ so the backup exists but the rollback fails.
        mocker.patch.object(
            transactions,
            "atomic_write_bytes",
            side_effect=OSError("Rollback failure mock"),
        )
        err_msg = "Simulated error"
        raise RuntimeError(err_msg)


def test_config_transaction_success(
    mock_asterisk_env: dict[str, Path],
) -> None:
    sip_conf = mock_asterisk_env["sip_conf"]

    with ConfigTransaction((sip_conf,)):
        sip_conf.write_text("modified content", encoding="utf-8")

    assert sip_conf.read_text(encoding="utf-8") == "modified content"


def test_config_transaction_rollback_on_exception(
    mock_asterisk_env: dict[str, Path],
) -> None:
    sip_conf = mock_asterisk_env["sip_conf"]
    original_content = sip_conf.read_text(encoding="utf-8")

    with pytest.raises(RuntimeError, match="Simulated error"):
        _corrupt_then_fail(sip_conf)

    assert sip_conf.read_text(encoding="utf-8") == original_content


def test_config_transaction_backup_failure_raises_exception(
    tmp_path: Path,
) -> None:
    non_existent_file = tmp_path / "missing.conf"

    with (
        pytest.raises(FileTransactionError, match="Backup failed for"),
        ConfigTransaction((non_existent_file,)),
    ):
        pass


def test_config_transaction_rollback_os_error_handling(
    mock_asterisk_env: dict[str, Path],
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed rollback is logged and the original error still propagates."""
    sip_conf = mock_asterisk_env["sip_conf"]
    with pytest.raises(RuntimeError, match="Simulated error"):
        _fail_with_broken_rollback(sip_conf, mocker)
    assert "CRITICAL: Failed to rollback sip.conf" in caplog.text


def _delete_backups_then_fail(path: Path) -> None:
    """Change a file, delete its backup, then raise to force a rollback.

    Args:
        path: The config file protected by the transaction.

    Raises:
        RuntimeError: Always, to trigger the rollback.
    """
    transaction = ConfigTransaction((path,))
    with transaction:
        for backup in transaction.backups.values():
            backup.unlink()
        path.write_text("changed", encoding="utf-8")
        err_msg = "Simulated error"
        raise RuntimeError(err_msg)


def test_config_transaction_rollback_skips_missing_backup(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """A backup deleted before rollback is skipped instead of crashing."""
    sip_conf = mock_asterisk_env["sip_conf"]
    with pytest.raises(RuntimeError, match="Simulated error"):
        _delete_backups_then_fail(sip_conf)
    assert sip_conf.read_text(encoding="utf-8") == "changed"


def _open_lock(path: Path) -> int:
    """Open the lock file the same way ConfigTransaction does.

    Args:
        path: The lock file.

    Returns:
        An open file descriptor.
    """
    return os.open(path, os.O_RDWR | os.O_CREAT, 0o600)


@pytest.fixture
def held_lock(mock_asterisk_env: dict[str, Path]) -> Generator[int]:
    """Hold the config lock, as another process would.

    Yields:
        The file descriptor holding the lock.
    """
    fd = _open_lock(mock_asterisk_env["lock_file"])
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        yield fd
    finally:
        os.close(fd)


def _assert_lock_free(sip_conf: Path) -> None:
    """Assert a new transaction can take the lock immediately.

    Args:
        sip_conf: Any file to protect in the probe transaction.
    """
    with ConfigTransaction((sip_conf,), lock_timeout=0):
        pass


@pytest.mark.usefixtures("held_lock")
def test_transaction_times_out_while_locked(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """A held lock makes the transaction give up without touching files."""
    sip_conf = mock_asterisk_env["sip_conf"]
    with (
        pytest.raises(FileTransactionError, match="Another change"),
        ConfigTransaction((sip_conf,), lock_timeout=0.2),
    ):
        pass
    assert list(mock_asterisk_env["backup_dir"].iterdir()) == []


def test_transaction_lock_released_after_success(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """After a normal exit, the next transaction gets the lock at once."""
    sip_conf = mock_asterisk_env["sip_conf"]
    with ConfigTransaction((sip_conf,), lock_timeout=0):
        pass
    _assert_lock_free(sip_conf)


def test_transaction_lock_released_after_error(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """After an error in the block, the lock is still released."""
    sip_conf = mock_asterisk_env["sip_conf"]
    with pytest.raises(RuntimeError, match="Simulated error"):
        _corrupt_then_fail(sip_conf)
    _assert_lock_free(sip_conf)


def test_transaction_lock_released_after_backup_failure(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """If a backup fails in __enter__, the lock is released anyway."""
    missing = mock_asterisk_env["etc_dir"] / "missing.conf"
    with (
        pytest.raises(FileTransactionError, match="Backup failed"),
        ConfigTransaction((missing,), lock_timeout=0),
    ):
        pass
    _assert_lock_free(mock_asterisk_env["sip_conf"])


def test_transaction_lock_released_after_rollback_failure(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """Even if the rollback itself fails, the lock is released."""
    sip_conf = mock_asterisk_env["sip_conf"]
    with pytest.raises(RuntimeError, match="Simulated error"):
        _fail_with_broken_rollback(sip_conf, mocker)
    mocker.stopall()
    _assert_lock_free(sip_conf)


def test_transaction_unopenable_lock_file(
    mock_asterisk_env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A lock file in a missing directory gives a clear error."""
    monkeypatch.setattr(
        transactions, "LOCK_FILE", tmp_path / "missing-dir" / "x.lock"
    )
    with (
        pytest.raises(FileTransactionError, match="Cannot open lock file"),
        ConfigTransaction((mock_asterisk_env["sip_conf"],), lock_timeout=0),
    ):
        pass


def test_transaction_waits_for_lock(
    mock_asterisk_env: dict[str, Path], held_lock: int
) -> None:
    """A transaction waits and succeeds once the other holder lets go."""
    release = threading.Timer(
        0.2, fcntl.flock, args=(held_lock, fcntl.LOCK_UN)
    )
    release.start()
    try:
        with ConfigTransaction(
            (mock_asterisk_env["sip_conf"],), lock_timeout=5
        ) as transaction:
            assert transaction.backups
    finally:
        release.cancel()


def test_transaction_holds_lock_inside_block(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """While a transaction is open, nobody else can take the lock."""
    with ConfigTransaction((mock_asterisk_env["sip_conf"],)):
        fd = _open_lock(mock_asterisk_env["lock_file"])
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)


def test_transaction_release_without_lock_is_harmless(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """Releasing when no lock is held does nothing and doesn't raise."""
    transaction = ConfigTransaction((mock_asterisk_env["sip_conf"],))
    transaction._release_lock()
    _assert_lock_free(mock_asterisk_env["sip_conf"])


def test_rollback_restores_without_temp_files(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """A rollback restores the original and leaves no temp files behind."""
    sip_conf = mock_asterisk_env["sip_conf"]
    original = sip_conf.read_text(encoding="utf-8")
    sip_conf.chmod(0o640)

    with pytest.raises(RuntimeError, match="Simulated error"):
        _corrupt_then_fail(sip_conf)

    assert sip_conf.read_text(encoding="utf-8") == original
    assert sip_conf.stat().st_mode & 0o777 == 0o640
    assert list(sip_conf.parent.glob(".*.tmp")) == []


@pytest.mark.parametrize(
    "original",
    [b"[general]\r\nport=5060\r\n", b"calf\xe9 latin-1\n"],
    ids=["crlf", "non-utf8"],
)
def test_rollback_is_byte_exact(
    mock_asterisk_env: dict[str, Path], original: bytes
) -> None:
    """Rollback restores the exact bytes, whatever the encoding."""
    sip_conf = mock_asterisk_env["sip_conf"]
    sip_conf.write_bytes(original)

    with pytest.raises(RuntimeError, match="Simulated error"):
        _corrupt_then_fail(sip_conf)

    assert sip_conf.read_bytes() == original


@pytest.mark.parametrize(
    "error", [OSError("disk full"), AsteriskCliError("permission denied")]
)
def test_backup_failure_is_reported_as_transaction_error(
    mock_asterisk_env: dict[str, Path],
    mocker: MockerFixture,
    error: Exception,
) -> None:
    """Expected backup failures become FileTransactionError."""
    mocker.patch.object(transactions, "backup_config_file", side_effect=error)

    with (
        pytest.raises(FileTransactionError, match="Backup failed"),
        ConfigTransaction((mock_asterisk_env["sip_conf"],), lock_timeout=0),
    ):
        pass


def test_unexpected_backup_error_is_not_disguised(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """A bug during backup surfaces as itself, and the lock is released."""
    sip_conf = mock_asterisk_env["sip_conf"]
    mocker.patch.object(
        transactions, "backup_config_file", side_effect=RuntimeError("bug")
    )

    with (
        pytest.raises(RuntimeError, match="bug"),
        ConfigTransaction((sip_conf,), lock_timeout=0),
    ):
        pass

    mocker.stopall()
    _assert_lock_free(sip_conf)
