"""Prompt user for MAC address and search config files for it."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from cli import read_mac_addr
from config import REQUIRED_FILES, TFTPBOOT, log

MatchRule = Callable[[str, str], bool]


@dataclass(frozen=True)
class MACMatch:
    """Information about found MAC addresses in a config file.

    Attributes:
        file_path: Path to the config file.
        line_number: Line number where the MAC address was found.
        matched_text: Text of the line that was matched.
    """

    file_path: Path
    line_number: int
    matched_text: str


def _is_sip_match(line_text: str, mac_address: str) -> bool:
    return f"[SEP{mac_address}]" in line_text


def _is_extensions_match(line_text: str, mac_address: str) -> bool:
    return f"SIP/SEP{mac_address}" in line_text


def scan_asterisk_file_for_mac_address(
    file_path: Path,
    mac_address: str,
    match_rule: Callable[[str, str], bool],
) -> Iterable[MACMatch]:
    """Search single Asterisk config file for a given MAC address.

    Args:
        file_path: Path to the config file to scan.
        mac_address: MAC address to search for.
        match_rule: Callable used to decide whether a line matches.

    Yields:
        MACMatch: Information about each match found.
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
    """Scan all ``.cnf.xml`` files in ``TFTPBOOT`` for a given MAC address.

    Args:
        mac_address: MAC address to search for.

    Yields:
        MACMatch: Information about the match.
    """
    xml_files: Iterable[Path] = TFTPBOOT.glob(pattern="*.cnf.xml")
    needle: str = f"<name>{mac_address}</name>"

    for file in xml_files:
        with file.open(mode="r", encoding="utf-8") as current_file:
            for line_number, line_text in enumerate(current_file, start=1):
                if needle in line_text.strip():
                    yield MACMatch(
                        file_path=file,
                        line_number=line_number,
                        matched_text=line_text.strip(),
                    )


def _log_matches(matches: Iterable[MACMatch]) -> int:
    """Log each match found and report how many were logged.

    Args:
        matches: Matches to log.

    Returns:
        The number of matches logged.
    """
    count: int = 0
    for match in matches:
        count += 1
        log.info(
            "[bold green]Match Found[/bold green] in %s (Line %d): %s",
            match.file_path.name,
            match.line_number,
            match.matched_text,
        )
    return count


def search_for_mac_address(mac_address: str | None) -> None:
    """Prompt for MAC address and search config files for it.

    Args:
        mac_address: MAC address to search for. If None, user
            is prompted to enter one.
    """
    if not mac_address:
        mac_address = read_mac_addr()

    scan_tasks: list[tuple[Path, MatchRule]] = [
        (REQUIRED_FILES["SIP_CONF"], _is_sip_match),
        (REQUIRED_FILES["EXTENSIONS_CONF"], _is_extensions_match),
    ]

    matches_found: int = 0
    for file_path, match_rule in scan_tasks:
        matches_found += _log_matches(
            scan_asterisk_file_for_mac_address(
                file_path=file_path,
                mac_address=mac_address,
                match_rule=match_rule,
            )
        )

    matches_found += _log_matches(scan_xml_files_for_mac_address(mac_address))

    if matches_found == 0:
        log.warning(
            "No reference to MAC address %s found in the config files.",
            mac_address,
        )


if __name__ == "__main__":
    search_for_mac_address(None)
