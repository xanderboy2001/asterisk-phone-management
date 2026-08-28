"""Domain models for Asterisk phone configuration."""

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar


@dataclass(frozen=True, kw_only=True)
class ConfigMatch:
    """Information about found MAC addresses or extensions in a config file.

    Attributes:
        file_path: Path to the config file.
        line_number: Line number where the MAC address was found.
        matched_text: Text of the line that was matched.
    """

    file_path: Path
    line_number: int
    matched_text: str


@dataclass(frozen=True, kw_only=True)
class Phone:
    """Information for phone registration.

    Attributes:
        extension: The 4-digit extension for the new phone.
        mac_address: The MAC address for the new phone.
        caller_id: The caller ID, if any, for the new phone.
    """

    extension: str
    mac_address: str
    caller_id: str


@dataclass(frozen=True, kw_only=True)
class Voicemail:
    """Information for voicemail.

    Attributes:
        name: Name of the person to send voicemails to.
        email: Email address of the person to send voicemails to.
    """

    name: str
    email: str


@dataclass(frozen=True, kw_only=True)
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

    # Field order exactly as emitted by `asterisk -rx "core show channels
    # concise"`, used to zip raw '!'-delimited output into keyword args.
    FIELD_ORDER: ClassVar[tuple[str, ...]] = (
        "channel",
        "context",
        "extension",
        "priority",
        "state",
        "application",
        "data",
        "caller_id_num",
        "caller_id_name",
        "account_code",
        "ama_flags",
        "duration",
        "bridged_channel",
    )
