"""A Python module to manage the Asterisk Phone system."""

import argparse
import logging
from pathlib import Path

import questionary
from questionary import Choice

from config import REQUIRED_FILES, console, log
from edit_files import edit_files
from register_phone import register_phone
from reload_asterisk import reload_asterisk
from remove_phone import remove_phone
from search_for_extension import search_for_extension
from search_for_mac_address import search_for_mac_address

MENU_OPTIONS: list[Choice] = [
    Choice(
        title="Search for Extension",
        description="Search config and xml files for a given extension.",
        value=[search_for_extension],
    ),
    Choice(
        title="Search for MAC Address",
        description="Search config and xml files for a given MAC address.",
        value=[search_for_mac_address],
    ),
    Choice(
        title="Register Phone",
        description="Register a new phone.",
        value=[register_phone, reload_asterisk],
    ),
    Choice(
        title="Delete Phone",
        description="Remove/deregister phone.",
        value=[remove_phone, reload_asterisk],
    ),
    Choice(
        title="Edit System Files",
        description="Edit an Asterisk config file.",
        value=[edit_files],
    ),
    Choice(
        title="Exit",
        description="Exit the program.",
        value="exit",
    ),
]


def _parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Command-line arguments to parse. Defaults to None, in
            which case ``sys.argv[1:]`` is used.

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
    """Verify that every path in ``REQUIRED_FILES`` exists.

    Every missing path is logged before an exception is raised, so a
    single run reports the full set of problems instead of stopping at
    the first one.

    Raises:
        FileNotFoundError: If any required file is missing.
    """
    missing: list[Path] = [
        path for path in REQUIRED_FILES if not path.exists()
    ]

    for path in missing:
        log.error("File '%s' not found!", path)

    if missing:
        msg = (
            f"Missing {len(missing)} required file(s): "
            f"{', '.join(str(p) for p in missing)}"
        )
        raise FileNotFoundError(msg)


def main() -> None:
    """Run the main application logic."""
    parsed_args = _parse_args()
    verbose: bool = parsed_args.verbose

    if verbose:
        log.setLevel(logging.DEBUG)
        log.debug("Verbose logging enabled.")

    ensure_required_paths()

    while True:
        selected = questionary.select(
            message="Choose an option:", choices=MENU_OPTIONS
        ).ask()

        if selected is None or selected == "exit":
            break

        for function in selected:
            console.print()
            function()
            console.print()


if __name__ == "__main__":
    main()
