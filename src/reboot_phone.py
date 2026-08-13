"""Reboot a phone via SSH."""

import re
import subprocess
import time

import paramiko

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


def _send_reboot_sequence(client: paramiko.SSHClient) -> None:
    shell = client.invoke_shell()
    time.sleep(0.5)

    commands: list[tuple[bytes, float]] = [
        (b"debug\n", 0.5),
        (b"debug\n", 0.5),
        (b"reboot\n", 1.0),
    ]

    for cmd, delay in commands:
        shell.send(cmd)
        time.sleep(delay)


def invoke_phone_reboot(
    ip_address: str, username: str, password: str, timeout: int = 5
) -> bool:
    """Invoke a reboot on a phone by its IP address and credentials.

    Args:
        ip_address: The IP address of the phone.
        username: The SSH username for the phone.
        password: The SSH password for the phone.
        timeout: The connection timeout in seconds. Defaults to 5.

    Returns:
        True if the reboot signal was sent successfully, False otherwise.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        log.info("Connecting to %s...", ip_address)
        client.connect(
            hostname=ip_address,
            username=username,
            password=password,
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
            disabled_algorithms={
                "pubkeys": [],
                "kex": [],
                "ciphers": [],
            },
        )
        _send_reboot_sequence(client)
    except (paramiko.SSHException, OSError) as e:
        if any(
            err in str(e)
            for err in [
                "Software caused connection abort",
                "Connection reset",
                "EOF",
            ]
        ):
            log.info(
                "Reboot signal sent successfully; host closed connection."
            )
            return True
        log.error("SSH error on %s: %s", ip_address, e)
        return False
    finally:
        client.close()

    log.info("successfully sent reboot command to %s", ip_address)
    return True


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
