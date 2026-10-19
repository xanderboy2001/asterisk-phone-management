"""Configuration file search utilities for extensions and MAC addresses."""

import re
from collections.abc import Callable, Iterable
from pathlib import Path

from asterisk_phone_management.core.constants import (
    CALLERID_DIRECTIVE,
    EXTENSIONS_CONF,
    SIP_CONF,
    TFTPBOOT,
    VOICEMAIL_CONF,
    VOICEMAIL_CONF_NAME,
    log,
)
from asterisk_phone_management.schemas.models import ConfigMatch

# Matches the mailbox number and the PIN field of a voicemail.conf entry.
_VM_PIN_RE = re.compile(r"^(\s*\d+\s*=>?\s*)[^,]*")

"""Type alias for callable rules to match lines during config file scanning."""
MatchRule = Callable[[str, str], bool]


def _redact_for_log(match: ConfigMatch) -> str:
    """Return a match's text with any voicemail PIN masked for logging.

    Args:
        match: The match to prepare for logging.

    Returns:
        The matched text, with the PIN replaced with ``****`` for
        voicemail.conf entries.
    """
    if match.file_path.name == VOICEMAIL_CONF_NAME:
        return _VM_PIN_RE.sub(r"\g<1>****", match.matched_text)
    return match.matched_text


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


def _is_caller_id_match(line_text: str, caller_id: str) -> bool:
    """Check if a line contains a caller ID match.

    Args:
        line_text: Line contents.
        caller_id: Target caller ID string.

    Returns:
        True if the line contains a matching caller ID False otherwise.
    """
    lower_line: str = line_text.lower()
    lower_caller_id: str = caller_id.lower()

    return (
        lower_line.startswith(CALLERID_DIRECTIVE)
        and lower_caller_id in lower_line
    )


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
            _redact_for_log(match),
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
        msg = (
            f"No reference to MAC address {mac_address}"
            " found in the config files."
        )
        log.warning(msg)

    return all_matches


def search_for_caller_id(caller_id: str) -> list[ConfigMatch]:
    """Search sip.conf for a given caller ID.

    Args:
        caller_id: The caller ID to search for.

    Returns:
        List of ConfigMatch dataclasses representing matches found.
    """
    all_matches: list[ConfigMatch] = []

    with SIP_CONF.open(mode="r", encoding="utf-8") as file:
        for line_number, line_text in enumerate(file, start=1):
            if _is_caller_id_match(line_text, caller_id):
                all_matches.append(
                    ConfigMatch(
                        file_path=SIP_CONF,
                        line_number=line_number,
                        matched_text=line_text,
                    )
                )
    return _log_and_collect_matches(all_matches)
