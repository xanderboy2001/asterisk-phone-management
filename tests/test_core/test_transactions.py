"""Unit tests for transactional config file backups and rollback context manager."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management.core.exceptions import FileTransactionError
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
        mocker.patch(
            "shutil.copyfile", side_effect=OSError("Rollback failure mock")
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
