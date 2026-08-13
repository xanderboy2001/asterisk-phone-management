"""Reboot a phone via SSH."""

import re
import subprocess

import pexpect

from cli import read_extension
from config import PHONE_SSH_PASS, PHONE_SSH_USER, log
from helpers import get_mac_from_ext
from search_for_extension import ExtensionMatch, search_for_extension


def get_ip_address(mac_address: str) -> str:
    """Get the IP address of a phone based on its MAC address.

    Args:
        mac_address: The MAC address of the phone.

    Returns:
        The IP address of the phone if found.

    Raises:
        SystemExit: If the IP address of the phone cannot be retrieved.
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
        log.error("Failed to get IP address of phone.")
        raise SystemExit(1) from e

    if not ip_address:
        log.error("Failed to get IP address of phone.")
        raise SystemExit(1)
    return ip_address


def _send_reboot_command(child: pexpect.spawn, password: str) -> None:
    child.expect("password:")
    child.sendline(password)

    child.expect("login:")
    child.sendline("debug")

    child.expect("Password:")
    child.sendline("debug")

    child.expect("DEBUG>")
    child.sendline("reboot")

    child.expect(pexpect.EOF)


def invoke_phone_reboot(
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
            Defaults to 10.


    Returns:
        True if the reboot command was Successfully sent and acknowledged,
        False if authentication failed, a prompt timed out,
            or process spawn failed.
    """
    ssh_cmd = f"ssh -t {username}@{ip_address}"

    log.info("Connecting to %s via SSH...", ip_address)
    try:
        child: pexpect.spawn = pexpect.spawn(
            command=ssh_cmd, encoding="utf-8", timeout=timeout
        )
        _send_reboot_command(child, password)

        log.info("Successfully sent reboot command to %s", ip_address)
        return True
    except (pexpect.TIMEOUT, pexpect.EOF):
        log.info(
            "Reboot signal sent to %s (connection closed by host).", ip_address
        )
        return True
    except (pexpect.ExceptionPexpect, OSError) as e:
        log.error("Failed to reboot phone via SSH: %s", e)
        return False


def reboot_phone() -> None:
    """Reboot a phone via SSH."""
    extension: str = read_extension()
    extension_matches: list[ExtensionMatch] = search_for_extension(extension)
    mac_address: str = get_mac_from_ext(extension_matches)
    ip_address: str = get_ip_address(mac_address)

    invoke_phone_reboot(
        ip_address=ip_address,
        username=PHONE_SSH_USER,
        password=PHONE_SSH_PASS,
    )


if __name__ == "__main__":
    reboot_phone()
