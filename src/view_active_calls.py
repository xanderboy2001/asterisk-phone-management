"""Module for viewing active Asterisk calls in a live updating terminal UI.

This script queries Asterisk for active channels and displays them
using the rich library to provide a human-readable, auto-refreshing panel.
"""

import subprocess
import time
from dataclasses import dataclass

from rich.align import Align
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from config import console, log

EXPECTED_FIELD_COUNT: int = 13


@dataclass
class ActiveCall:
    """Represents an active Asterisk channel mapped from 'concise' output.

    Attributes:
        channel: The channel name.
        context: The current context.
        extension: The current extension.
        priority: The current priority.
        state: The state of the channel.
        application: The current application.
        data: Data passed to the application.
        caller_id_num: The Caller ID number.
        caller_id_name: The Caller ID name.
        account_code: The account code.
        ama_flags: The AMA flags.
        duration: Call duration in seconds.
        bridged_channel: The channel this is bridged to.
    """

    channel: str
    context: str
    extension: str
    priority: str
    state: str
    application: str
    data: str
    caller_id_num: str
    caller_id_name: str
    account_code: str
    ama_flags: str
    duration: str
    bridged_channel: str


def get_active_calls() -> list[ActiveCall]:
    """Fetch active calls from Asterisk and parse them into dataclasses.

    Returns:
        list[ActiveCall]: A list of active calls. Returns an empty list if
        Asterisk is unreachable or not installed.
    """
    try:
        result = subprocess.run(
            ["asterisk", "-rx", "core show channels concise"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    calls = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue

        parts = line.split("!")

        if len(parts) >= EXPECTED_FIELD_COUNT:
            calls.append(ActiveCall(*parts[:EXPECTED_FIELD_COUNT]))

    return calls


def format_duration(seconds_str: str) -> str:
    """Convert a string of raw seconds into a formatted time string.

    Args:
        seconds_str: The duration in raw seconds.

    Returns:
        Formatted duration as HH:MM:SS or MM:SS. If parsing fails,
        it returns the original string.
    """
    try:
        total_seconds = int(seconds_str)
    except ValueError as e:
        log.error(
            "Error when converting seconds string into an integer: %s", e
        )
        return seconds_str

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def generate_table(calls: list[ActiveCall]) -> Table:
    """Generate a Rich Table from a list of ActiveCall objects.

    Args:
        calls: A list of active call objects.

    Returns:
        Table: A populated rich Table displaying the active calls.
    """
    table = Table(
        show_header=True,
        show_footer=True,
        header_style="bold magenta",
        footer_style="dim italic",
        expand=True,
    )

    table.add_column(header="Channel", footer="The active endpoint.")
    table.add_column("Caller ID", footer="Source (Who called)")
    table.add_column("Extension", footer="Target (Dialed number)")
    table.add_column("State", footer="Call Status")
    table.add_column("Duration", justify="right", footer="Time active")
    table.add_column("Bridged Channel", footer="Connected to")

    if not calls:
        table.add_row("No active calls currently.", "", "", "", "", "")
        return table

    for call in calls:
        caller_id = (
            f"{call.caller_id_name} <{call.caller_id_num}>"
            if call.caller_id_name
            else call.caller_id_num
        )
        human_duration = format_duration(call.duration)
        table.add_row(
            call.channel,
            caller_id,
            call.extension,
            call.state,
            human_duration,
            call.bridged_channel,
        )
    return table


def render_panel() -> None:
    """Initialize and runs the live auto-updating watcher for active calls.

    Create a live rich dashboard that polls Asterisk every second.
    """
    with Live(console=console, screen=True, auto_refresh=True) as live:
        while True:
            calls = get_active_calls()

            table = generate_table(calls)
            panel = Panel(
                Align.center(table),
                title="[bold yellow]Active Asterisk Calls[/bold yellow]",
                subtitle="[dim]Press Ctrl+C to exit[/dim]",
                border_style="blue",
            )

            live.update(panel)
            time.sleep(1)


def view_active_calls() -> None:
    """Main entry point for the script."""
    try:
        render_panel()
    except KeyboardInterrupt:
        log.warning("User exited watcher.")
        return


if __name__ == "__main__":
    view_active_calls()
