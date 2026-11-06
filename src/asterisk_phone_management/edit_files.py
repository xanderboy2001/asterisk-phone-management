"""Select and edit configuration files using an interactive menu."""

import shlex
import shutil
import subprocess
from pathlib import Path

import questionary
from questionary import Choice

from asterisk_phone_management.cli.prompts import ask
from asterisk_phone_management.core.constants import log
from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    FileTransactionError,
)
from asterisk_phone_management.core.settings import get_settings
from asterisk_phone_management.core.transactions import ConfigTransaction

# Tried in order after $EDITOR.
_FALLBACK_EDITORS: tuple[str, ...] = ("nvim", "vim", "nano")


def _editor_argv(command: str) -> list[str] | None:
    """Split an editor command line and check the program is installed.

    Args:
        command: An editor command, which may include arguments,
        e.g. ``code --wait`` or ``"/opt/My Editor/bin/ed" -w``.

    Returns:
        The command split into arguments, or None if it is empty, can't
        be parsed, or its program isn't installed.
    """
    try:
        argv = shlex.split(command)
    except ValueError:
        log.warning("Ignoring editor %r: it can't be parsed.", command)
        return None
    if not argv or shutil.which(argv[0]) is None:
        return None
    return argv


def get_editor() -> list[str] | None:
    """Determine the user's preferred editor.

    Uses ``$EDITOR`` if it names an installed program, otherwise the
    first installed editor from nvim, vim, and nano.

    Returns:
        The editor command split into arguments, e.g. ``["code", "--wait"]``,
        or None if no usable editor is found.
    """
    candidates = [get_settings().editor, *_FALLBACK_EDITORS]
    for candidate in candidates:
        argv = _editor_argv(candidate)
        if argv is not None:
            return argv
    return None


def edit_files() -> None:
    """Prompt user to select a configuration file and open it in an editor.

    The selected file is backed up before editing and rolled back if the
    editor exits with a non-zero status.

    Raises:
        AsteriskCliError: If no valid editor could be found.
        FileTransactionError: If the editor exits with a non-zero status
            or otherwise fails to run.
    """
    file_choices: list[Choice] = [
        Choice(
            title=get_settings().sip_conf.name,
            value=get_settings().sip_conf,
        ),
        Choice(
            title=get_settings().extensions_conf.name,
            value=get_settings().extensions_conf,
        ),
        Choice(
            title=get_settings().voicemail_conf.name,
            value=get_settings().voicemail_conf,
        ),
    ]

    selected_file: Path = ask(
        questionary.select(
            message="Choose a file to edit",
            choices=file_choices,
            use_shortcuts=True,
        ),
        Path,
    )
    editor_argv = get_editor()
    if editor_argv is None:
        msg = "No valid editor found!"
        log.error(msg)
        raise AsteriskCliError(msg)

    try:
        with ConfigTransaction((selected_file,)):
            subprocess.run([*editor_argv, str(selected_file)], check=True)
    except (subprocess.CalledProcessError, OSError) as e:
        msg = f"Editor session for {selected_file.name} failed: {e}"
        log.error(msg)
        raise FileTransactionError(msg) from e
