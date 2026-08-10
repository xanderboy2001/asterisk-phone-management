"""Prompt user for extension and search config files for it."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from cli import read_extension
from config import REQUIRED_FILES, TFTPBOOT, log

MatchRule = Callable[[str, str], bool]


@dataclass(frozen=True)
class ExtensionMatch:
    """Information about found extensions in a config file.

    Attributes:
        file_path: Path to the config file.
        line_number: Line number where extension was found.
        matched_text: Text of the line that was matched.
    """

    file_path: Path
    line_number: int
    matched_text: str


def _is_sip_match(line_text: str, extension: str) -> bool:
    return f"<{extension}>" in line_text


def _is_extensions_match(line_text: str, extension: str) -> bool:
    return line_text.strip().startswith(f"exten => {extension}")


def _is_voicemail_match(line_text: str, extension: str) -> bool:
    return line_text.strip().startswith(extension)


def scan_asterisk_file_for_extension(
    file_path: Path,
    target_extension: str,
    match_rule: Callable[[str, str], bool],
) -> Iterable[ExtensionMatch]:
    """Search single asterisk config file for a given extension.

    Args:
        file_path: Path to the config file to scan.
        target_extension: Extension to search for.
        match_rule: Match rule to use.

    Yields:
        ExtensionMatch: Information about each match found.
    """
    with file_path.open(mode="r", encoding="utf-8") as current_file:
        for line_number, line_text in enumerate(current_file, start=1):
            if match_rule(line_text, target_extension):
                yield ExtensionMatch(
                    file_path=file_path,
                    line_number=line_number,
                    matched_text=line_text.strip(),
                )


def scan_xml_files_for_extension(
    target_extension: str,
) -> Iterable[ExtensionMatch]:
    """Scan all ``.cnf.xml`` files in ``TFTPBOOT`` for a given extension.

    Args:
        target_extension: Extension to search for.

    Yields:
        ExtensionMatch: Information about each match found.
    """
    xml_files: Iterable[Path] = TFTPBOOT.glob(pattern="*.cnf.xml")
    needle: str = f"<featureLabel>{target_extension}</featureLabel>"

    for file in xml_files:
        with file.open(mode="r", encoding="utf-8") as current_file:
            for line_number, line_text in enumerate(current_file, start=1):
                if needle in line_text.strip():
                    yield ExtensionMatch(
                        file_path=file,
                        line_number=line_number,
                        matched_text=line_text.strip(),
                    )


def _log_matches(matches: Iterable[ExtensionMatch]) -> int:
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


def search_for_extension(extension: str | None) -> None:
    """Prompt for extension and search config files for it.

    Args:
        extension: The extension to search for.
            If not provided, prompts user to enter one.
    """
    if not extension:
        extension = read_extension()

    scan_tasks: list[tuple[Path, MatchRule]] = [
        (REQUIRED_FILES["SIP_CONF"], _is_sip_match),
        (REQUIRED_FILES["EXTENSIONS_CONF"], _is_extensions_match),
        (REQUIRED_FILES["VOICEMAIL_CONF"], _is_voicemail_match),
    ]

    matches_found: int = 0
    for file_path, match_rule in scan_tasks:
        matches_found += _log_matches(
            scan_asterisk_file_for_extension(
                file_path=file_path,
                target_extension=extension,
                match_rule=match_rule,
            )
        )

    matches_found += _log_matches(
        matches=scan_xml_files_for_extension(extension)
    )

    if matches_found == 0:
        log.warning(
            "No references to extension %s were found in the config files.",
            extension,
        )


if __name__ == "__main__":
    search_for_extension(None)
