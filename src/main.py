"""A Python module to manage the Asterisk Phone system."""

import argparse
import logging

import questionary

from globals import REQUIRED_FILES, log
from search_for_extension import search_for_extension
from search_for_mac_address import search_for_mac_address

MENU_OPTIONS: list[questionary.Choice] = [
    questionary.Choice(
        title="Search for Extension",
        description="Search config and xml files for a given extension.",
        value=search_for_extension,
    ),
    questionary.Choice(
        title="Search for MAC Address",
        description="Search config and xml files for a given MAC address.",
        value=search_for_mac_address,
    ),
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
