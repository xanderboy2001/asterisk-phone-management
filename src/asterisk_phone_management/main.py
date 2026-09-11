"""A Python module to manage the Asterisk Phone system."""

import argparse
import logging
from pathlib import Path

import questionary
from questionary import Choice

from asterisk_phone_management.cli.handlers import (
    handle_edit_caller_id,
    handle_reboot_phone,
    handle_register_phone,
    handle_remove_phone,
    handle_replace_phone,
    handle_reset_vm_password,
    handle_search_for_caller_id,
    handle_search_for_extension,
    handle_search_for_mac_address,
    handle_toggle_call_forwarding,
)
from asterisk_phone_management.cli.views import view_active_calls
from asterisk_phone_management.core.constants import (
    REQUIRED_FILES,
    console,
    log,
)
from asterisk_phone_management.core.exceptions import AsteriskCliError
from asterisk_phone_management.edit_files import edit_files
from asterisk_phone_management.services.device_actions import reload_asterisk

MENU_OPTIONS: list[Choice] = [
    Choice(
        title="Reload Asterisk",
        description=(
            "Reload the Asterisk service to account "
            "for changes made to config files."
        ),
        value=reload_asterisk,
    ),
    Choice(
        title="Search for Extension",
        description="Search config and xml files for a given extension.",
        value=handle_search_for_extension,
    ),
    Choice(
        title="Search for MAC Address",
        description="Search config and xml files for a given MAC address.",
        value=handle_search_for_mac_address,
    ),
    Choice(
        title="Search for Caller ID",
        description="Search sip.conf for a given caller ID.",
        value=handle_search_for_caller_id,
    ),
    Choice(
        title="Register Phone",
        description="Register a new phone.",
        value=handle_register_phone,
    ),
    Choice(
        title="Delete Phone",
        description="Remove/deregister phone.",
        value=handle_remove_phone,
    ),
    Choice(
        title="Replace Phone",
        description="Replace a physical phone.",
        value=handle_replace_phone,
    ),
    Choice(
        title="Edit System Files",
        description="Edit an Asterisk config file.",
        value=edit_files,
    ),
    Choice(
        title="Reset Voicemail Password",
        description="Reset a voicemail box password.",
        value=handle_reset_vm_password,
    ),
    Choice(
        title="Edit a Caller ID",
        description="Change a phone's caller ID.",
        value=handle_edit_caller_id,
    ),
    Choice(
        title="Toggle Call Forwarding",
        description="Enable or disable call forwarding for a user.",
        value=handle_toggle_call_forwarding,
    ),
    Choice(
        title="Reboot Phone",
        description="Reboot a phone.",
        value=handle_reboot_phone,
    ),
    Choice(title="View Active Calls", value=view_active_calls),
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
    """Run the main application logic.

    Raises:
        SystemExit: If any of the required files are not found.
    """
    parsed_args = _parse_args()
    verbose: bool = parsed_args.verbose

    if verbose:
        log.setLevel(logging.DEBUG)
        log.debug("Verbose logging enabled.")

    try:
        ensure_required_paths()
    except FileNotFoundError as err:
        log.error(str(err))
        raise SystemExit(1) from err

    while True:
        selected = questionary.select(
            message="Choose an option:",
            choices=MENU_OPTIONS,
            use_shortcuts=True,
        ).ask()

        if selected is None or selected == "exit":
            break

        console.print()
        try:
            selected()
        except KeyboardInterrupt:
            log.warning("Operation cancelled by user.")
        except AsteriskCliError as err:
            log.error("Operation failed: %s", err)
        console.print()
