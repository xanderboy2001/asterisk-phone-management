"""Select and edit configuration files using an interactive menu."""

import os
import shutil
import subprocess
from pathlib import Path

import questionary
from questionary import Choice

from asterisk_phone_management.cli.prompts import ask
from asterisk_phone_management.core.constants import (
    EXTENSIONS_CONF,
    SIP_CONF,
    VOICEMAIL_CONF,
    log,
)
from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    FileTransactionError,
)
from asterisk_phone_management.core.transactions import ConfigTransaction


def get_editor() -> str | None:
    """Determine the user's preferred editor.

    Checks environment variables and common editor names.

    Returns:
        The name of the selected editor or None if no valid editor is found.
    """
    candidates = [os.getenv("EDITOR"), "nvim", "vim", "nano"]
    return next((cmd for cmd in candidates if cmd and shutil.which(cmd)), None)


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
            title=SIP_CONF.name,
            value=SIP_CONF,
        ),
        Choice(
            title=EXTENSIONS_CONF.name,
            value=EXTENSIONS_CONF,
        ),
        Choice(
            title=VOICEMAIL_CONF.name,
            value=VOICEMAIL_CONF,
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
    editor = get_editor()
    if not editor:
        msg = "No valid editor found!"
        log.error("No valid editor found!")
        raise AsteriskCliError(msg)

    try:
        with ConfigTransaction((selected_file,)):
            subprocess.run([editor, str(selected_file)], check=True)
    except (subprocess.CalledProcessError, OSError) as e:
        msg = f"Editor session for {selected_file.name} failed: {e}"
        log.error(msg)
        raise FileTransactionError(msg) from e
