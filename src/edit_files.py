"""Select and edit configuration files using an interactive menu."""

import os
import shutil
import subprocess
from pathlib import Path

import questionary
from questionary import Choice

from config import EXTENSIONS_CONF, SIP_CONF, VOICEMAIL_CONF, log


def get_editor() -> str | None:
    """Determine the user's preferred editor.

    Checks environment variables and common editor names.

    Returns:
        The name of the selected editor or None if no valid editor is found.
    """
    candidates = [os.getenv("EDITOR"), "nvim", "vim", "nano"]
    return next((cmd for cmd in candidates if cmd and shutil.which(cmd)), None)


def edit_files() -> None:
    """Prompt user to select a configuration file and opens it in an editor."""
    selected_file: Path | None = None

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

    selected_file = questionary.select(
        message="Choose a file to edit",
        choices=file_choices,
        use_shortcuts=True,
    ).ask()

    if selected_file is None:
        log.error("No file selected to edit.")
        return

    editor = get_editor()
    if not editor:
        log.error("No valid editor found!")
        return

    subprocess.run([editor, str(selected_file)], check=True)


if __name__ == "__main__":
    edit_files()
