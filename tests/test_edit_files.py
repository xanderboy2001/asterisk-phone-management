"""Unit tests for the edit_files command utility."""

import subprocess
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management import edit_files as edit_files_module
from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    FileTransactionError,
)
from asterisk_phone_management.edit_files import edit_files

SPACED_EDITOR = "/opt/My Editor/bin/ed"


@pytest.fixture
def installed(mocker: MockerFixture) -> set[str]:
    """Pretend only the commands in the returned set are installed.

    Tests can remove commands from the set to simulate missing editors.

    Returns:
        The mutable set of installed commands.
    """
    commands = {"nvim", "vim", "nano", "code", SPACED_EDITOR}

    def _which(cmd: str) -> str | None:
        if cmd not in commands:
            return None
        return cmd if cmd.startswith("/") else f"/usr/bin/{cmd}"

    mocker.patch.object(edit_files_module.shutil, "which", side_effect=_which)
    return commands


@pytest.fixture
def sip_conf(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> Path:
    """Choose sip.conf at the file prompt.

    Returns:
        The test sip.conf path.
    """
    path = mock_asterisk_env["sip_conf"]
    mocker.patch("questionary.select").return_value.ask.return_value = path
    return path


def _set_editor(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    """Set or unset $EDITOR for one test.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        value: The value to use, or None to unset it.
    """
    if value is None:
        monkeypatch.delenv("EDITOR", raising=False)
    else:
        monkeypatch.setenv("EDITOR", value)


def _run_editor(mocker: MockerFixture) -> list[str]:
    """Run edit_files with the editor mocked and return its command line.

    Args:
        mocker: The pytest-mock fixture.

    Returns:
        The argument list the editor was started with.
    """
    mock_run = mocker.patch.object(edit_files_module.subprocess, "run")
    edit_files()
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs.get("check") is True
    return list(mock_run.call_args.args[0])


@pytest.mark.usefixtures("installed")
def test_uses_editor_from_env(
    sip_conf: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plain $EDITOR command opens the chosen file."""
    _set_editor(monkeypatch, "nano")

    argv = _run_editor(mocker)

    assert Path(argv[0]).name == "nano"
    assert argv[1:] == [str(sip_conf)]


@pytest.mark.usefixtures("installed")
def test_editor_with_arguments(
    sip_conf: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """$EDITOR arguments are passed before the file path."""
    _set_editor(monkeypatch, "code --wait")

    argv = _run_editor(mocker)

    assert Path(argv[0]).name == "code"
    assert argv[1:] == ["--wait", str(sip_conf)]


@pytest.mark.usefixtures("installed")
def test_editor_quoted_path_with_spaces(
    sip_conf: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A quoted editor path containing spaces is one command."""
    _set_editor(monkeypatch, f'"{SPACED_EDITOR}" -w')

    argv = _run_editor(mocker)

    assert argv == [SPACED_EDITOR, "-w", str(sip_conf)]


@pytest.mark.usefixtures("installed")
@pytest.mark.parametrize(
    "editor",
    [None, "", "   ", "not-installed --flag", 'vim "unclosed'],
    ids=["unset", "empty", "blank", "not-installed", "bad-quoting"],
)
def test_unusable_editor_falls_back_to_nvim(
    sip_conf: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    editor: str | None,
) -> None:
    """An unset, empty, missing, or unparsable $EDITOR is skipped."""
    _set_editor(monkeypatch, editor)

    argv = _run_editor(mocker)

    assert Path(argv[0]).name == "nvim"
    assert argv[1:] == [str(sip_conf)]


@pytest.mark.parametrize(
    ("missing", "expected"),
    [({"nvim"}, "vim"), ({"nvim", "vim"}, "nano")],
    ids=["no-nvim", "no-nvim-or-vim"],
)
@pytest.mark.usefixtures("sip_conf")
def test_fallback_order(
    installed: set[str],
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    missing: set[str],
    expected: str,
) -> None:
    """Without $EDITOR, nvim, vim, and nano are tried in that order."""
    installed -= missing
    _set_editor(monkeypatch, None)

    argv = _run_editor(mocker)

    assert Path(argv[0]).name == expected


@pytest.mark.usefixtures("sip_conf")
def test_no_editor_found(
    installed: set[str], mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no usable editor, nothing is run and the user is told."""
    installed.clear()
    _set_editor(monkeypatch, "code --wait")
    mock_run = mocker.patch.object(edit_files_module.subprocess, "run")

    with pytest.raises(AsteriskCliError, match="No valid editor found"):
        edit_files()

    mock_run.assert_not_called()


@pytest.mark.usefixtures("installed")
def test_editor_failure_rolls_back(
    sip_conf: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the editor exits with an error, the file is restored."""
    _set_editor(monkeypatch, None)
    original = sip_conf.read_text(encoding="utf-8")

    def _break_then_fail(*_args: object, **_kwargs: object) -> None:
        sip_conf.write_text("broken", encoding="utf-8")
        raise subprocess.CalledProcessError(1, "nvim")

    mocker.patch.object(
        edit_files_module.subprocess, "run", side_effect=_break_then_fail
    )

    with pytest.raises(
        FileTransactionError, match=r"Editor session for .* failed"
    ):
        edit_files()

    assert sip_conf.read_text(encoding="utf-8") == original


@pytest.mark.usefixtures("installed")
def test_ctrl_c_in_editor_rolls_back(
    sip_conf: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ctrl+C while editing propagates and restores the file."""
    _set_editor(monkeypatch, None)
    original = sip_conf.read_text(encoding="utf-8")

    def _break_then_interrupt(*_args: object, **_kwargs: object) -> None:
        sip_conf.write_text("broken", encoding="utf-8")
        raise KeyboardInterrupt

    mocker.patch.object(
        edit_files_module.subprocess, "run", side_effect=_break_then_interrupt
    )

    with pytest.raises(KeyboardInterrupt):
        edit_files()

    assert sip_conf.read_text(encoding="utf-8") == original


def test_no_file_selected(mocker: MockerFixture) -> None:
    """Cancelling the file prompt cancels the operation."""
    mocker.patch("questionary.select").return_value.ask.return_value = None

    with pytest.raises(KeyboardInterrupt):
        edit_files()
