"""A Python module to manage the Asterisk Phone system."""

import argparse
import logging
from pathlib import Path
from typing import Final

import questionary
from rich.console import Console
from rich.logging import RichHandler

from search_for_extension import search_for_extension

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


MENU_OPTIONS: Final[list[questionary.Choice]] = [
    questionary.Choice(
        title="Search for Extension",
        description="Search config and xml files for a given extension.",
        value=search_for_extension,
    )
]


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


def main() -> None:
    """Run the main application logic."""
    parsed_args = _parse_args()
    verbose: bool = parsed_args.verbose

    if verbose:
        log.setLevel(logging.DEBUG)
        log.debug("Verbose logging enabled.")

    ensure_required_paths()

    selected = questionary.select(
        message="Choose and option:", choices=MENU_OPTIONS
    ).ask()

    if selected:
        selected()


if __name__ == "__main__":
    main()
