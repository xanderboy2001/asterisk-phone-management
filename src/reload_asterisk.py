"""Check Asterisk process status and reload configuration modules."""

import shutil
import subprocess

from config import log


def is_asterisk_running() -> bool:
    """Check if the Asterisk process is currently running under pgrep.

    Returns:
        True if the Asterisk process is running, False otherwise.

    Raises:
        SystemExit: If the 'pgrep' command is missing or execution fails.
    """
    pgrep_path: str | None = shutil.which("pgrep")
    if not pgrep_path:
        log.error("The 'pgrep' command was not found on the system.")
        raise SystemExit(1)

    try:
        result = subprocess.run(
            [pgrep_path, "-x", "asterisk"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        log.error("Failed to check if Asterisk is running: %s", e)
        raise SystemExit(1) from e


def reload_asterisk_module(command: str, friendly_name: str) -> None:
    """Reloads a specific Asterisk module using the Asterisk CLI.

    Args:
        command: The CLI command to execute (e.g., 'sip reload').
        friendly_name: Human-readable name of the module for log messages.

    Raises:
        SystemExit: If the 'asterisk' executable is missing or execution fails.
    """
    asterisk_path: str | None = shutil.which("asterisk")
    if not asterisk_path:
        log.error("The 'asterisk' command was not found on the system.")
        raise SystemExit

    log.info("Reloading %s...", friendly_name)
    try:
        subprocess.run(
            [asterisk_path, "-rx", command],
            check=True,
            capture_output=True,
            text=True,
        )
        log.info("%s reloaded successfully.", friendly_name.capitalize())
    except subprocess.CalledProcessError as e:
        log.error("Failed to reload %s", friendly_name)
        log.error("Command error output: %s", e.stderr.strip())
        raise SystemExit(1) from e


def reload_asterisk() -> None:
    """Executes the reload workflow for all configured Asterisk modules.

    Raises:
        SystemExit: If Asterisk is not running or any module fails to reload.
    """
    if not is_asterisk_running():
        log.error(
            "Asterisk is not running. Please start Asterisk and try again."
        )
        raise SystemExit(1)

    reload_tasks: list[dict[str, str]] = [
        {"command": "voicemail reload", "name": "voicemail configuration"},
        {"command": "sip reload", "name": "SIP configuration"},
        {"command": "dialplan reload", "name": "dialplan"},
    ]

    for task in reload_tasks:
        reload_asterisk_module(
            command=task["command"], friendly_name=task["name"]
        )

    log.info("All configurations reloaded successfully.")


if __name__ == "__main__":
    reload_asterisk()
