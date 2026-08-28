"""UI view rendering using Rich."""

import time

from rich.align import Align
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from asterisk_phone_management.core.globals import console, log
from asterisk_phone_management.schemas.models import (
    ActiveCall,
    Phone,
    Voicemail,
)
from asterisk_phone_management.services.device_actions import get_active_calls


def print_phone_table(
    phone: Phone, voicemail: Voicemail | None = None
) -> None:
    """Print the information for a new phone in a Rich table.

    Args:
        phone: Phone dataclass containing extension, MAC, and caller ID.
        voicemail: Optional Voicemail dataclass containing name and email.
    """
    table = Table(title="Phone Information")

    table.add_column(header="Extension")
    table.add_column(header="MAC Address")
    row_values: list[str] = [phone.extension, phone.mac_address]

    if phone.caller_id:
        table.add_column(header="Caller ID")
        row_values.append(phone.caller_id)

    if voicemail:
        table.add_column(header="Voicemail Name")
        table.add_column(header="Voicemail Email")
        row_values.extend([voicemail.name, voicemail.email])

    table.add_row(*row_values)

    console.print(table)


def _format_duration(seconds_str: str) -> str:
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


def _generate_call_table(calls: list[ActiveCall]) -> Table:
    """Generate a Rich Table from a list of ActiveCall objects.

    Args:
        calls: A list of active call objects.

    Returns:
        A populated rich Table displaying the active calls.
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
        human_duration = _format_duration(call.duration)
        table.add_row(
            call.channel,
            caller_id,
            call.extension,
            call.state,
            human_duration,
            call.bridged_channel,
        )
    return table


def _render_call_panel() -> None:
    """Initialize and run the live auto-updating watcher for active calls.

    Create a live rich dashboard that polls Asterisk every second.
    """
    with Live(console=console, screen=True, auto_refresh=True) as live:
        while True:
            calls = get_active_calls()

            table = _generate_call_table(calls)
            panel = Panel(
                Align.center(table),
                title="[bold yellow]Active Asterisk Calls[/bold yellow]",
                subtitle="[dim]Press Ctrl+C to exit[/dim]",
                border_style="blue",
            )

            live.update(panel)
            time.sleep(1)


def view_active_calls() -> None:
    """Watch and render active calls until the user exits."""
    try:
        _render_call_panel()
    except KeyboardInterrupt:
        log.warning("User exited watcher.")
