"""Unit tests for the edit_files command utility."""

import contextlib
import subprocess
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    FileTransactionError,
)
from asterisk_phone_management.edit_files import edit_files, get_editor


def test_get_editor_found(mocker: MockerFixture) -> None:
    mocker.patch("os.getenv", return_value=None)
    mocker.patch(
        "shutil.which",
        side_effect=lambda x: "/usr/bin/nvim" if x == "nvim" else None,
    )

    assert get_editor() == "nvim"


def test_get_editor_from_env(mocker: MockerFixture) -> None:
    mocker.patch("os.getenv", return_value="custom_editor")
    mocker.patch(
        "shutil.which", side_effect=lambda x: f"/usr/bin/{x}" if x else None
    )
    assert get_editor() == "custom_editor"


def test_get_editor_not_found(mocker: MockerFixture) -> None:
    mocker.patch("os.getenv", return_value=None)
    mocker.patch("shutil.which", return_value=None)

    assert get_editor() is None


def test_edit_files_no_selection(mocker: MockerFixture) -> None:
    mocker.patch("questionary.select").return_value.ask.return_value = None
    edit_files()


def test_edit_files_success(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    sip_conf = mock_asterisk_env["sip_conf"]
    mocker.patch("questionary.select").return_value.ask.return_value = sip_conf
    mocker.patch("src.edit_files.get_editor", return_value="nvim")
    mock_run = mocker.patch("subprocess.run")

    edit_files()

    mock_run.assert_called_once_with(["nvim", str(sip_conf)], check=True)


def test_edit_files_no_editor_raises_error(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    sip_conf = mock_asterisk_env["sip_conf"]
    mocker.patch("questionary.select").return_value.ask.return_value = sip_conf
    mocker.patch("src.edit_files.get_editor", return_value=None)

    with pytest.raises(AsteriskCliError, match="No valid editor found"):
        edit_files()


def test_edit_files_editor_error_rolls_back(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    sip_conf = mock_asterisk_env["sip_conf"]
    mocker.patch("questionary.select").return_value.ask.return_value = sip_conf
    mocker.patch("src.edit_files.get_editor", return_value="nvim")
    mocker.patch(
        "subprocess.run", side_effect=subprocess.CalledProcessError(1, "nvim")
    )

    with pytest.raises(
        FileTransactionError, match=r"Editor session for .* failed"
    ):
        edit_files()


def test_edit_files_internal_keyboard_interrupt(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    sip_conf = mock_asterisk_env["sip_conf"]
    mocker.patch("questionary.select").return_value.ask.return_value = sip_conf
    mocker.patch("src.edit_files.get_editor", return_value="nvim")
    mocker.patch("subprocess.run", side_effect=KeyboardInterrupt)
    with pytest.raises(KeyboardInterrupt):
        edit_files()


def test_edit_files_keyboard_interrupt(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    sip_conf = mock_asterisk_env["sip_conf"]
    mocker.patch("questionary.select").return_value.ask.return_value = sip_conf
    mocker.patch("src.edit_files.get_editor", return_value="nvim")
    mocker.patch("subprocess.run", side_effect=KeyboardInterrupt)

    with contextlib.suppress(KeyboardInterrupt):
        edit_files()
