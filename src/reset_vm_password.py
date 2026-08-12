"""Reset voicemail password for given extension."""

import re
from pathlib import Path

import questionary

from cli import read_extension
from config import MINIMUM_VM_PASSWORD_LENGTH, VOICEMAIL_CONF, console, log
from helpers import backup_config_file, safe_exit
from search_for_extension import search_for_extension


def validate_vm_password(password: str) -> bool | str:
    """Validate the voicemail password.

    Args:
        password: The new voicemail password to validate.

    Returns:
        True if the password is valid,
            otherwise a string with an error message.
    """
    if len(password) < MINIMUM_VM_PASSWORD_LENGTH or not password.isdigit():
        return (
            "Password must be at least a "
            f"{MINIMUM_VM_PASSWORD_LENGTH}-digit number."
        )
    return True


def read_new_password(extension: str) -> str:
    """Read and validate the new voicemail PIN from user input.

    Args:
        extension: The extension for which the new PIN is being set.

    Returns:
        The validated new voicemail PIN.

    Raises:
        SystemExit: If no password is provided.
    """
    new_password = questionary.text(
        message="Enter the new voicemail PIN:",
        default=extension,
        validate=validate_vm_password,
        instruction=(
            "Enter a number at least "
            f"{MINIMUM_VM_PASSWORD_LENGTH} digits long."
        ),
    ).ask()

    if not new_password:
        log.error("No password provided!")
        raise SystemExit(1)

    return new_password


def reset_vm_password() -> None:
    """Reset the voicemail password for a given extension.

    Raises:
        SystemExit: If no password is provided
            or if the voicemail box for the extension is not found.
    """
    extension = read_extension()

    extension_matches = search_for_extension(extension)

    voicemail_match = [
        match
        for match in extension_matches
        if match.file_path.name == "voicemail.conf"
    ]

    if not voicemail_match:
        log.error(
            "Voicemail box for extension %s not found in %s.",
            extension,
            VOICEMAIL_CONF,
        )
        raise SystemExit(1)

    log.info("Voicemail box for extension %s found.", extension)

    new_pin = read_new_password(extension)

    backups: dict[Path, Path] = {}

    backups[VOICEMAIL_CONF] = backup_config_file(VOICEMAIL_CONF)

    try:
        content = VOICEMAIL_CONF.read_text(encoding="utf-8")
        pattern = rf"^({re.escape(extension)}\s*=>?\s*)[^,]*"
        updated_content = re.sub(
            pattern=pattern,
            repl=rf"\g<1>{new_pin}",
            string=content,
            flags=re.MULTILINE,
        )
        VOICEMAIL_CONF.write_text(updated_content, encoding="utf-8")
    except (PermissionError, OSError) as e:
        log.error("Failed to modify %s: %s", VOICEMAIL_CONF, e)
        safe_exit(backups=backups)

    console.print(voicemail_match)


if __name__ == "__main__":
    reset_vm_password()
