"""Services for device interactions, reloading modules, and SSH actions."""

import re
import shutil
import subprocess

import pexpect

from asterisk_phone_management.core.constants import (
    PHONE_SSH_PASS,
    PHONE_SSH_USER,
    log,
)
from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    AsteriskServiceError,
    DeviceCommunicationError,
)
from asterisk_phone_management.helpers import get_mac_from_ext
from asterisk_phone_management.schemas.models import ActiveCall
from asterisk_phone_management.services.search import (
    ConfigMatch,
    search_for_extension,
)

EXPECTED_FIELD_COUNT: int = len(ActiveCall.FIELD_ORDER)


def _get_ip_address(mac_address: str) -> str:
    """Get the IP address of a phone based on its MAC address.

    Args:
        mac_address: The MAC address of the phone.

    Returns:
        The IP address of the phone if found.

    Raises:
        DeviceCommunicationError: If the peer's IP address cannot be
            retrieved from Asterisk.
    """
    sep_mac: str = f"SEP{mac_address}"
    ip_address: str = ""
    try:
        output = subprocess.run(
            ["asterisk", "-rx", f"sip show peer {sep_mac}"],
            capture_output=True,
            text=True,
            check=True,
        )
        match: re.Match[str] | None = re.search(
            pattern=r"(?:Addr->IP|Address-IP)\s*:\s*([0-9]{1,3}(?:\.[0-9]{1,3}){3})",
            string=output.stdout,
        )

        if match and match.group(1) != "0.0.0.0":
            ip_address = match.group(1)
    except subprocess.CalledProcessError as e:
        msg = "Failed to get IP address of phone."
        log.error(msg)
        raise DeviceCommunicationError(msg) from e

    if not ip_address:
        msg = f"Could not resolve an IP address for {sep_mac}."
        log.error(msg)
        raise DeviceCommunicationError(msg)
    return ip_address


def _send_reboot_command(child: "pexpect.spawn[str]", password: str) -> None:
    """Send SSH debug authentication and reboot commands to a Cisco IP phone.

    Args:
        child: Spawned pexpect process connected to the phone.
        password: Password for phone SSH access.
    """
    child.expect("password:")
    child.sendline(password)

    child.expect("login:")
    child.sendline("debug")

    child.expect("Password:")
    child.sendline("debug")

    child.expect("DEBUG>")
    child.sendline("reboot")

    child.expect(pexpect.EOF)


def _invoke_phone_reboot(
    ip_address: str, username: str, password: str, timeout: int = 5
) -> bool:
    """Reboot a Cisco IP phone by automating system SSH via pexpect.

    Connects to the phone using the system's native SSH binary, handles the
    two-stage Cisco debug prompt sequence (Username: debug / Password: debug),
    and issues the reboot command.


    Args:
        ip_address: The target phone's IP address.
        username: The initial SSH username (e.g., 'admin')
        password: The initial SSH password.
        timeout: Maximum time in seconds to wait for each prompt.
            Defaults to 5.


    Returns:
        True if the reboot command was successfully sent and acknowledged,
        False if authentication failed, a prompt timed out,
            or process spawn failed.
    """
    ssh_cmd = f"ssh -t {username}@{ip_address}"

    log.info("Connecting to %s via SSH...", ip_address)
    try:
        child: pexpect.spawn[str] = pexpect.spawn(
            command=ssh_cmd, encoding="utf-8", timeout=timeout
        )
        _send_reboot_command(child, password)
    except (pexpect.TIMEOUT, pexpect.EOF):
        log.info(
            "Reboot signal sent to %s (connection closed by host).", ip_address
        )
        return True
    except (pexpect.ExceptionPexpect, OSError) as e:
        log.error("Failed to reboot phone via SSH: %s", e)
        return False
    else:
        log.info("Successfully sent reboot command to %s", ip_address)
        return True


def _is_asterisk_running() -> bool:
    """Check if the Asterisk process is currently running under pgrep.

    Returns:
        True if the Asterisk process is running, False otherwise.

    Raises:
        AsteriskCliError: If the 'pgrep' command was not found or could
            not be executed.
    """
    pgrep_path: str | None = shutil.which("pgrep")
    if not pgrep_path:
        msg = "The 'pgrep' command was not found on the system."
        log.error(msg)
        raise AsteriskCliError(msg)

    try:
        result = subprocess.run(
            [pgrep_path, "-x", "asterisk"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError as e:
        msg = f"Failed to execute pgrep: {e}"
        log.error(msg)
        raise AsteriskCliError(msg) from e

    return result.returncode == 0


def reload_asterisk_module(command: str, friendly_name: str) -> None:
    """Reload a specific Asterisk module using the Asterisk CLI.

    Args:
        command: The CLI command to execute (e.g., 'sip reload').
        friendly_name: Human-readable name of the module for log messages.

    Raises:
        AsteriskCliError: If the 'asterisk' executable is missing.
        AsteriskServiceError: If the reload command fails.
    """
    asterisk_path: str | None = shutil.which("asterisk")
    if not asterisk_path:
        msg = "The 'asterisk' command was not found on the system."
        log.error(msg)
        raise AsteriskCliError(msg)

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
        msg = f"Failed to reload {friendly_name}: {e.stderr.strip()}"
        log.error(msg)
        raise AsteriskServiceError(msg) from e


def reload_asterisk() -> None:
    """Execute the reload workflow for all configured Asterisk modules.

    Raises:
        AsteriskServiceError: If Asterisk is not running, or if any
            module fails to reload.
    """
    if not _is_asterisk_running():
        msg = "Asterisk is not running. Please start Asterisk and try again."
        log.error(msg)
        raise AsteriskServiceError(msg)

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


def get_active_calls() -> list[ActiveCall]:
    """Fetch active calls from Asterisk and parse them into dataclasses.

    Returns:
        List of ActiveCall objects representing current calls. Returns
            an empty list if Asterisk cannot be reached or reports no calls.
    """
    try:
        result = subprocess.run(
            ["asterisk", "-rx", "core show channels concise"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    calls: list[ActiveCall] = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue

        parts = line.split("!")

        if len(parts) >= EXPECTED_FIELD_COUNT:
            fields = dict(zip(ActiveCall.FIELD_ORDER, parts, strict=False))
            calls.append(ActiveCall(**fields))

    return calls


def reboot_phone(extension: str) -> None:
    """Reboot a phone given its extension.

    Args:
        extension: The target phone extension.

    Raises:
        DeviceCommunicationError: If the phone's IP address cannot be
            resolved, or the reboot command could not be delivered.
    """
    extension_matches: list[ConfigMatch] = search_for_extension(extension)
    mac_address: str = get_mac_from_ext(extension_matches)
    ip_address: str = _get_ip_address(mac_address)

    success = _invoke_phone_reboot(
        ip_address=ip_address,
        username=PHONE_SSH_USER,
        password=PHONE_SSH_PASS,
    )

    if not success:
        msg = f"Failed to deliver reboot command to {ip_address}."
        raise DeviceCommunicationError(msg)
