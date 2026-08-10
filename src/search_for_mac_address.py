"""Prompt user for MAC address and search config files for it."""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

import questionary

from config import MAC_ADDRESS_LENGTH, REQUIRED_FILES, TFTPBOOT, log


@dataclass
class MACMatch:
    """Dataclass to hold information about found MAC addresses in config files.

    Attributes:
        file_path: Path to the config file.
        line_number: Line number where the MAC address was found.
        matched_text: Text of the line that was matched.
    """

    file_path: Path
    line_number: int
    matched_text: str


def validate_mac_addr(mac_address: str) -> bool | str:
    """Check if given MAC address is valid.

    Args:
        mac_address: The MAC address to validate.

    Returns:
        True if the MAC address is valid, otherwise an error message.
    """
    raw_mac: str = re.sub(r"[:\-.]", "", mac_address).upper()
    if len(raw_mac) != MAC_ADDRESS_LENGTH:
        return "MAC address must be 12 digits."

    if not re.fullmatch(r"^[0-9A-F]{12}$", raw_mac):
        return "MAC address must contain hexadecimal characters."

    return True


def read_mac_addr() -> str:
    """Ask the user to provide an MAC address.

    Returns:
        Validated MAC address.
    """
    response = None
    while response is None:
        response = questionary.text(
            message="Enter a MAC address "
            + "(e.g., AABBCCDDEEFF, AA:BB:CC:DD:EE:FF)",
            validate=validate_mac_addr,
        ).ask()

    return response.upper()


def _is_sip_match(line_text: str, mac_address: str) -> bool:
    return f"[SEP{mac_address}]" in line_text


def _is_extensions_match(line_text: str, mac_address: str) -> bool:
    return f"SIP/SEP{mac_address}" in line_text


def scan_asterisk_file_for_mac_address(
    file_path: Path,
    mac_address: str,
    match_rule: Callable[[str, str], bool],
) -> Iterable[MACMatch]:
    """Search provided asterisk config file for a given MAC address.

    Args:
        file_path: Path to the config file to scan.
        mac_address: Extension to search for.
        match_rule: Match rule to use.

    Yields:
        MACMatch: Object containing information about the match.
    """
    with file_path.open(mode="r", encoding="utf-8") as current_file:
        for line_number, line_text in enumerate(current_file, start=1):
            if match_rule(line_text, mac_address):
                yield MACMatch(
                    file_path=file_path,
                    line_number=line_number,
                    matched_text=line_text.strip(),
                )


def scan_xml_files_for_mac_address(mac_address: str) -> Iterable[MACMatch]:
    """Scan all .cnf.xml files in globals.TFTPBOOT for a given MAC address.

    Args:
        mac_address: The MAC address to search for.

    Yields:
        MACMatch: Object containing information about the match.
    """
    xml_files: Iterable[Path] = TFTPBOOT.glob(pattern="*.cnf.xml")

    for file in xml_files:
        with file.open(mode="r", encoding="utf-8") as current_file:
            for line_number, line_text in enumerate(current_file, start=1):
                if f"<name>{mac_address}</name>" in line_text.strip():
                    yield MACMatch(
                        file_path=file,
                        line_number=line_number,
                        matched_text=line_text.strip(),
                    )


def search_for_mac_address() -> None:
    """Prompt for MAC address and search config files for it."""
    mac_address: str = read_mac_addr()

    scan_tasks: list[tuple[Path, Callable[[str, str], bool]]] = [
        (REQUIRED_FILES["SIP_CONF"], _is_sip_match),
        (REQUIRED_FILES["EXTENSIONS_CONF"], _is_extensions_match),
    ]

    matches_found: int = 0
    for file_path, match_rule in scan_tasks:
        for match in scan_asterisk_file_for_mac_address(
            file_path=file_path,
            mac_address=mac_address,
            match_rule=match_rule,
        ):
            matches_found += 1
            log.info(
                "[bold green]Match Found[/bold green] in %s (Line %d): %s",
                match.file_path.name,
                match.line_number,
                match.matched_text,
            )
        for match in scan_xml_files_for_mac_address(mac_address=mac_address):
            matches_found += 1
            log.info(
                "[bold green]Match Found[/bold green] in %s (Line %d): %s",
                match.file_path.name,
                match.line_number,
                match.matched_text,
            )
        if matches_found == 0:
            log.warning(
                "No reference to MAC address %s found in the config files.",
                mac_address,
            )


if __name__ == "__main__":
    search_for_mac_address()
