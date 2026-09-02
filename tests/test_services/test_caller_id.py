"""Unit tests for caller ID service functions."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management.core.exceptions import FileTransactionError
from asterisk_phone_management.schemas.models import ConfigMatch
from asterisk_phone_management.services.caller_id import (
    _apply_caller_id_updates,
    edit_caller_id,
)


def test_apply_caller_id_updates_success() -> None:
    """Test _apply_caller_id_updates applies changes to correct lines."""
    lines = [
        "[general]",
        "[SEP112233445566](phone)",
        'callerid="Old" <1001>',
        "secret=password",
    ]
    result = _apply_caller_id_updates(lines, [2], '"New" <1001>')
    assert result[2] == 'callerid="New" <1001>'
    assert result[0] == "[general]"  # Unchanged


def test_apply_caller_id_updates_invalid_index() -> None:
    """Test _apply_caller_id_updates raises on invalid index."""
    lines = ["[general]", "callerid=test"]
    with pytest.raises(FileTransactionError, match="out of range"):
        _apply_caller_id_updates(lines, [5], '"New" <1001>')


def test_apply_caller_id_updates_negative_index() -> None:
    """Test _apply_caller_id_updates raises on negative index."""
    lines = ["[general]", "callerid=test"]
    with pytest.raises(FileTransactionError, match="out of range"):
        _apply_caller_id_updates(lines, [-1], '"New" <1001>')


def test_apply_caller_id_updates_line_mismatch() -> None:
    """Test _apply_caller_id_updates raises when line doesn't have callerid."""
    lines = ["[general]", "secret=password"]
    with pytest.raises(
        FileTransactionError, match="expected callerid directive"
    ):
        _apply_caller_id_updates(lines, [1], '"New" <1001>')


@pytest.mark.usefixtures("mock_asterisk_env")
def test_edit_caller_id_success(mock_asterisk_env: dict[str, Path]) -> None:
    """Test edit_caller_id updates caller ID in sip.conf."""
    sip_conf = mock_asterisk_env["sip_conf"]
    sip_conf.write_text(
        "[general]\n[SEP112233445566](phone)\n"
        'callerid="Old" <1001>\nsecret=password\n',
        encoding="utf-8",
    )

    edit_caller_id(
        [
            ConfigMatch(
                file_path=sip_conf,
                line_number=3,
                matched_text='callerid="Old" <1001>',
            )
        ],
        '"New" <1001>',
    )


def test_edit_caller_id_empty_targets() -> None:
    """Test edit_caller_id returns early with empty targets."""
    edit_caller_id([], '"New" <1001>')


@pytest.mark.usefixtures("mock_asterisk_env")
def test_edit_caller_id_file_error(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """Test edit_caller_id raises on file write error."""
    sip_conf = mock_asterisk_env["sip_conf"]
    sip_conf.write_text(
        "[general]\ncallerid=test\n",
        encoding="utf-8",
    )

    mocker.patch(
        "pathlib.Path.read_text",
        side_effect=OSError("Read error"),
    )

    with pytest.raises(FileTransactionError):
        edit_caller_id(
            [
                ConfigMatch(
                    file_path=sip_conf,
                    line_number=2,
                    matched_text="callerid=test",
                )
            ],
            '"New" <1001>',
        )
