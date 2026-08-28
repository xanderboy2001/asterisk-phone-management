"""Unit tests for main function."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management.core.exceptions import AsteriskCliError
from asterisk_phone_management.main import (
    _parse_args,
    ensure_required_paths,
    main,
)


def test_parse_args_default() -> None:
    args_default = _parse_args([])
    assert args_default.verbose is False


def test_parse_args_verbose() -> None:
    args_default = _parse_args(["-v"])
    assert args_default.verbose is True


@pytest.mark.usefixtures("mock_asterisk_env")
def test_ensure_required_paths_success(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.main.Path.exists",
        return_value=True,
    )
    ensure_required_paths()


def test_ensure_required_paths_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_file = tmp_path / "nonexistent.conf"
    monkeypatch.setattr(
        "asterisk_phone_management.main.REQUIRED_FILES",
        (missing_file,),
    )

    with pytest.raises(FileNotFoundError, match="Missing 1 required file"):
        ensure_required_paths()


def test_main_missing_files_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    missing_file = tmp_path / "nonexistent.conf"
    monkeypatch.setattr(
        "asterisk_phone_management.main.REQUIRED_FILES", (missing_file,)
    )
    mocker.patch("asterisk_phone_management.main._parse_args")

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1


@pytest.mark.usefixtures("mock_asterisk_env")
def test_main_menu_loop_execution(mocker: MockerFixture) -> None:
    mocker.patch("asterisk_phone_management.main.ensure_required_paths")
    mocker.patch(
        "asterisk_phone_management.main._parse_args",
        return_value=mocker.MagicMock(verbose=True),
    )

    action_normal = mocker.MagicMock()
    action_keyboard_interrupt = mocker.MagicMock(side_effect=KeyboardInterrupt)
    action_asterisk_error = mocker.MagicMock(
        side_effect=AsteriskCliError("Custom error")
    )
    action_general_error = mocker.MagicMock(
        side_effect=Exception("Unknown execution error")
    )

    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.side_effect = [
        action_normal,
        action_keyboard_interrupt,
        action_asterisk_error,
        action_general_error,
        "exit",
    ]

    with pytest.raises(Exception, match="Unknown execution error"):
        main()

    assert action_normal.call_count == 1
    assert action_keyboard_interrupt.call_count == 1
    assert action_asterisk_error.call_count == 1
    assert action_general_error.call_count == 1


def test_main_menu_cancelled_none(mocker: MockerFixture) -> None:
    mocker.patch("asterisk_phone_management.main.ensure_required_paths")
    mocker.patch(
        "asterisk_phone_management.main._parse_args",
        return_value=mocker.MagicMock(verbose=False),
    )
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = None
    main()


def test_main_menu_keyboard_interrupt(mocker: MockerFixture) -> None:
    mocker.patch("asterisk_phone_management.main.ensure_required_paths")
    mocker.patch(
        "asterisk_phone_management.main._parse_args",
        return_value=mocker.MagicMock(verbose=False),
    )
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.side_effect = KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        main()
