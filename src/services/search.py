"""Configuration file search utilities for extensions and MAC addresses."""

from collections.abc import Callable, Iterable
from pathlib import Path

from src.core.globals import (
    EXTENSIONS_CONF,
    SIP_CONF,
    TFTPBOOT,
    VOICEMAIL_CONF,
    log,
)
from src.schemas.models import ConfigMatch

MatchRule = Callable[[str, str], bool]


def _is_sip_ext_match(line_text: str, extension: str) -> bool:
    """Check if a sip.conf line contains an extension reference.

    Args:
        line_text: Line contents.
        extension: Target extension string.

    Returns:
        True if matching, False otherwise.
    """
    return f"<{extension}>" in line_text


def _is_extensions_ext_match(line_text: str, extension: str) -> bool:
    """Check if an extensions.conf line defines the extension.

    Args:
        line_text: Line contents.
        extension: Target extension string.

    Returns:
        True if matching, False otherwise.
    """
    return line_text.strip().startswith(f"exten => {extension}")


def _is_voicemail_ext_match(line_text: str, extension: str) -> bool:
    """Check if a voicemail.conf line defines the extension mailbox.

    Args:
        line_text: Line contents.
        extension: Target extension string.

    Returns:
        True if matching, False otherwise.
    """
    return line_text.strip().startswith(extension)


def _is_sip_mac_match(line_text: str, mac_address: str) -> bool:
    """Check if a sip.conf line defines a device section for a MAC address.

    Args:
        line_text: Line contents.
        mac_address: Target MAC address string.

    Returns:
        True if matching, False otherwise.
    """
    return f"[SEP{mac_address}]" in line_text


def _is_extensions_mac_match(line_text: str, mac_address: str) -> bool:
    """Check if an extensions.conf line references a device SIP channel.

    Args:
        line_text: Line contents.
        mac_address: Target MAC address string.

    Returns:
        True if matching, False otherwise.
    """
    return f"SIP/SEP{mac_address}" in line_text


def _log_and_collect_matches(
    matches: Iterable[ConfigMatch],
) -> list[ConfigMatch]:
    """Log each match found and report how many were logged.

    Args:
        matches: Matches to log.

    Returns:
        A list of ConfigMatch objects.
    """
    collected: list[ConfigMatch] = []
    for match in matches:
        log.info(
            "[bold green]Match Found[/bold green] in %s (Line %d): %s",
            match.file_path.name,
            match.line_number,
            match.matched_text,
        )
        collected.append(match)
    return collected


def scan_asterisk_file_for_extension(
    file_path: Path,
    target_extension: str,
    match_rule: Callable[[str, str], bool],
) -> Iterable[ConfigMatch]:
    """Search single asterisk config file for a given extension.

    Args:
        file_path: Path to the config file to scan.
        target_extension: Extension to search for.
        match_rule: Match rule to use.

    Yields:
        ConfigMatch: Information about each match found.
    """
    with file_path.open(mode="r", encoding="utf-8") as current_file:
        for line_number, line_text in enumerate(current_file, start=1):
            if match_rule(line_text, target_extension):
                yield ConfigMatch(
                    file_path=file_path,
                    line_number=line_number,
                    matched_text=line_text.strip(),
                )


def scan_asterisk_file_for_mac_address(
    file_path: Path,
    mac_address: str,
    match_rule: Callable[[str, str], bool],
) -> Iterable[ConfigMatch]:
    """Search single Asterisk config file for a given MAC address.

    Args:
        file_path: Path to the config file to scan.
        mac_address: MAC address to search for.
        match_rule: Callable used to decide whether a line matches.

    Yields:
        ConfigMatch: Information about each match found.
    """
    with file_path.open(mode="r", encoding="utf-8") as current_file:
        for line_number, line_text in enumerate(current_file, start=1):
            if match_rule(line_text, mac_address):
                yield ConfigMatch(
                    file_path=file_path,
                    line_number=line_number,
                    matched_text=line_text.strip(),
                )


def scan_xml_files_for_extension(
    target_extension: str,
) -> Iterable[ConfigMatch]:
    """Scan all ``.cnf.xml`` files in ``TFTPBOOT`` for a given extension.

    Args:
        target_extension: Extension to search for.

    Yields:
        ConfigMatch: Information about each match found.
    """
    xml_files: Iterable[Path] = TFTPBOOT.glob(pattern="*.cnf.xml")
    needle: str = f"<featureLabel>{target_extension}</featureLabel>"

    for file in xml_files:
        with file.open(mode="r", encoding="utf-8") as current_file:
            for line_number, line_text in enumerate(current_file, start=1):
                if needle in line_text.strip():
                    yield ConfigMatch(
                        file_path=file,
                        line_number=line_number,
                        matched_text=line_text.strip(),
                    )


def scan_xml_files_for_mac_address(mac_address: str) -> Iterable[ConfigMatch]:
    """Scan all ``.cnf.xml`` files in ``TFTPBOOT`` for a given MAC address.

    Args:
        mac_address: MAC address to search for.

    Yields:
        ConfigMatch: Information about the match.
    """
    xml_files: Iterable[Path] = TFTPBOOT.glob(pattern="*.cnf.xml")
    needle: str = f"<name>{mac_address}</name>"

    for file in xml_files:
        with file.open(mode="r", encoding="utf-8") as current_file:
            for line_number, line_text in enumerate(current_file, start=1):
                if needle in line_text.strip():
                    yield ConfigMatch(
                        file_path=file,
                        line_number=line_number,
                        matched_text=line_text.strip(),
                    )


def search_for_extension(extension: str) -> list[ConfigMatch]:
    """Search all config and XML files for a given extension.

    Args:
        extension: The extension to search for.

    Returns:
        List of ConfigMatch dataclasses representing matches found.
    """
    scan_tasks: list[tuple[Path, MatchRule]] = [
        (SIP_CONF, _is_sip_ext_match),
        (EXTENSIONS_CONF, _is_extensions_ext_match),
        (VOICEMAIL_CONF, _is_voicemail_ext_match),
    ]

    all_matches: list[ConfigMatch] = []

    for file_path, match_rule in scan_tasks:
        if not file_path.exists():
            continue
        found = scan_asterisk_file_for_extension(
            file_path=file_path,
            target_extension=extension,
            match_rule=match_rule,
        )
        all_matches.extend(_log_and_collect_matches(found))

    all_matches.extend(
        _log_and_collect_matches(scan_xml_files_for_extension(extension))
    )

    if not all_matches:
        log.warning(
            "No references to extension %s were found in the config file.",
            extension,
        )

    return all_matches


def search_for_mac_address(mac_address: str) -> list[ConfigMatch]:
    """Search all config and XML files for a given MAC address.

    Args:
        mac_address: MAC address to search for.

    Returns:
        List of ConfigMatch dataclasses representing matches found.
    """
    scan_tasks: list[tuple[Path, MatchRule]] = [
        (SIP_CONF, _is_sip_mac_match),
        (EXTENSIONS_CONF, _is_extensions_mac_match),
    ]

    all_matches: list[ConfigMatch] = []

    for file_path, match_rule in scan_tasks:
        if not file_path.exists():
            continue
        found = scan_asterisk_file_for_mac_address(
            file_path=file_path,
            mac_address=mac_address,
            match_rule=match_rule,
        )
        all_matches.extend(_log_and_collect_matches(found))

    all_matches.extend(
        _log_and_collect_matches(scan_xml_files_for_mac_address(mac_address))
    )

    if not all_matches:
        log.warning(
            "No reference to MAC address %s found in the config files.",
            mac_address,
        )

    return all_matches
