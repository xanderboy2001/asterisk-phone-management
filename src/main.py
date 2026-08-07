"""A Python module to manage the Asterisk Phone system."""

import argparse
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import questionary
from rich.console import Console
from rich.logging import RichHandler

console = Console()


FORMAT = "%(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True, markup=True)],
)

log = logging.getLogger("rich")

# ETC_ASTERISK: Path = Path("/etc/asterisk")
ETC_ASTERISK: Path = Path(Path(__file__).parent.parent / "config/asterisk")
# TFTPBOOT: Path = Path("/var/lib/tftpboot")
TFTPBOOT: Path = Path(Path(__file__).parent.parent / "config/tftpboot")
# Required files + paths
REQUIRED_FILES: Final[dict[str, Path]] = {
    "SIP_CONF": ETC_ASTERISK / "sip.conf",
    "EXTENSIONS_CONF": ETC_ASTERISK / "extensions.conf",
    "VOICEMAIL_CONF": ETC_ASTERISK / "voicemail.conf",
    "XML_TEMPLATE": TFTPBOOT / "SEP0000000.cnf.xml",
}

EXTENSION_LENGTH: Final[int] = 4


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


def _parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Command-line arguments to parse.
            Defaults to None.

    Returns:
        The parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="A Python module to manage the Asterisk Phone system."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        required=False,
        help="Enable verbose logging.",
    )

    return parser.parse_args(args)


def ensure_required_paths() -> None:
    """Check for existence of all paths in REQUIRED_FILES.

    Raises:
        FileNotFoundError: if a file doesn't exist.
    """
    for file in REQUIRED_FILES.values():
        if not file.exists():
            log.error("File '%s' not found!", file)
            raise FileNotFoundError(file)


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


def main() -> None:
    """Run the main application logic."""
    parsed_args = _parse_args()
    verbose: bool = parsed_args.verbose

    if verbose:
        log.setLevel(logging.DEBUG)
        log.debug("Verbose logging enabled.")

    ensure_required_paths()

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
    if matches_found == 0:
        log.warning(
            "No references to extension %s were found in the config files.",
            target_extension,
        )


if __name__ == "__main__":
    main()
