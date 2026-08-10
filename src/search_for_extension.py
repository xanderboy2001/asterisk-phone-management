"""Prompt user for extension and search config files for it."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

import questionary

from globals import EXTENSION_LENGTH, REQUIRED_FILES, TFTPBOOT, log


@dataclass
class ExtensionMatch:
    """Dataclass to hold information about found extensions in config files.

    Attributes:
        file_path: Path to the config file.
        line_number: Line number where extension was found.
        matched_text: Text of the line that was matched.
    """

    file_path: Path
    line_number: int
    matched_text: str


def validate_extension(extension: str) -> bool | str:
    """Check if given extension is valid.

    Args:
        extension: The extension to validate.

    Returns:
        True if extension is valid, otherwise an error message.
    """
    if len(extension) != EXTENSION_LENGTH or not extension.isdigit():
        return "Extension must be 4 digits."

    return True


def read_extension() -> str:
    """Ask the user to provide an extension.

    Returns:
        Validated extension.
    """
    response = None
    while response is None:
        response = questionary.text(
            message="Enter a 4-digit extension (e.g., 1234)",
            validate=validate_extension,
        ).ask()

    return response


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
    """Search provided asterisk config file for a given extension.

    Args:
        file_path: Path to the config file to scan.
        target_extension: Extension to search for.
        match_rule: Match rule to use.

    Yields:
        ExtensionMatch: Object containing information about the match.
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
    """Scan all .cnf.xml files in /var/tftpboot for a given extension.

    Args:
        target_extension: Extension to search for.

    Yields:
        ExtensionMatch: Object containing information about the match.
    """
    xml_files: Iterable[Path] = TFTPBOOT.glob(pattern="*.cnf.xml")

    for file in xml_files:
        with file.open(mode="r", encoding="utf-8") as current_file:
            for line_number, line_text in enumerate(current_file, start=1):
                if (
                    f"<featureLabel>{target_extension}</featureLabel>"
                    in line_text.strip()
                ):
                    yield ExtensionMatch(
                        file_path=file,
                        line_number=line_number,
                        matched_text=line_text.strip(),
                    )


def search_for_extension() -> None:
    """Prompt for extension and search config files for it."""
    target_extension: str = read_extension()

    scan_tasks: list[tuple[Path, Callable[[str, str], bool]]] = [
        (REQUIRED_FILES["SIP_CONF"], _is_sip_match),
        (REQUIRED_FILES["EXTENSIONS_CONF"], _is_extensions_match),
        (REQUIRED_FILES["VOICEMAIL_CONF"], _is_voicemail_match),
    ]

    matches_found: int = 0
    for file_path, match_rule in scan_tasks:
        for match in scan_asterisk_file_for_extension(
            file_path=file_path,
            target_extension=target_extension,
            match_rule=match_rule,
        ):
            matches_found += 1
            log.info(
                "[bold green]Match Found[/bold green] in %s (Line %d): %s",
                match.file_path.name,
                match.line_number,
                match.matched_text,
            )
        for match in scan_xml_files_for_extension(
            target_extension=target_extension
        ):
            matches_found += 1
            log.info(
                "[bold green]Match Found[/bold green] in %s (Line %d): %s",
                match.file_path.name,
                match.line_number,
                match.matched_text,
            )
    if matches_found == 0:
        log.warning(
            "No references to extension %s were found in the config files.",
            target_extension,
        )


if __name__ == "__main__":
    search_for_extension()
