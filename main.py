"""A Python module to manage the Asterisk Phone system."""

import argparse
import logging

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


def main() -> None:
    """Run the main application logic."""
    parsed_args = _parse_args()
    verbose: bool = parsed_args.verbose

    if verbose:
        log.setLevel(logging.DEBUG)
        log.debug("Verbose logging enabled.")


if __name__ == "__main__":
    main()
