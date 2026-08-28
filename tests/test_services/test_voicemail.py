"""Unit tests for voicemail management service."""

from pathlib import Path

import pytest

from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    FileTransactionError,
)
from asterisk_phone_management.services.voicemail import reset_vm_password


def test_reset_vm_password_success(mock_asterisk_env: dict[str, Path]) -> None:
    """Verify voicemail password reset replaces PIN in voicemail.conf.

    Args:
        mock_asterisk_env: Environment fixture providing mock file paths.
    """
    vm_conf = mock_asterisk_env["vm_conf"]

    reset_vm_password("1001", "5678")

    updated_content = vm_conf.read_text(encoding="utf-8")
    assert "1001 = 5678," in updated_content


@pytest.mark.usefixtures("mock_asterisk_env")
def test_reset_vm_password_extension_not_found() -> None:
    """Verify reset_vm_password raises AsteriskCliError for missing mailbox."""
    with pytest.raises(
        AsteriskCliError, match="Voicemail box for extension 9999 not found"
    ):
        reset_vm_password("9999", "5678")


@pytest.mark.usefixtures("mock_asterisk_env")
def test_reset_vm_password_file_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify reset_vm_password converts OSError into FileTransactionError.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """

    def _mock_write_text(*_args: object, **_kwargs: object) -> None:
        err_msg = "Permission denied"
        raise OSError(err_msg)

    monkeypatch.setattr(Path, "write_text", _mock_write_text)

    with pytest.raises(FileTransactionError, match="Failed to modify"):
        reset_vm_password("1001", "5678")
