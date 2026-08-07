"""A Python module to manage the Asterisk Phone system."""

import argparse
import logging
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
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)

log = logging.getLogger("rich")

ETC_ASTERISK: Path = Path("/etc/asterisk")
TFTPBOOT: Path = Path("/var/lib/tftpboot")
# Required files + paths
REQUIRED_FILES: Final[dict[str, Path]] = {
    "SIP_CONF": ETC_ASTERISK / "sip.conf",
    "EXTENSIONS_CONF": ETC_ASTERISK / "extensions.conf",
    "VOICEMAIL_CONF": ETC_ASTERISK / "voicemail.conf",
    "XML_TEMPLATE": TFTPBOOT / "SEP0000000.cnf.xml",
}

EXTENSION_LENGTH: Final[int] = 4


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


def main() -> None:
    """Run the main application logic."""
    parsed_args = _parse_args()
    verbose: bool = parsed_args.verbose

    if verbose:
        log.setLevel(logging.DEBUG)
        log.debug("Verbose logging enabled.")

    ensure_required_paths()


if __name__ == "__main__":
    main()
