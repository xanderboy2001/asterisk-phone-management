"""Application-wide constants and shared configuration.

This module centralizes constants, required file paths, and logging
configuration used across the Asterisk phone management tool.
"""

import logging
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

from asterisk_phone_management.core.theme import DRACULA

# Load environment variables from a .env file if present in the current
# working directory.
load_dotenv()

MAC_ADDRESS_LENGTH: int = 12
EXTENSION_LENGTH: int = 4
MINIMUM_VM_PASSWORD_LENGTH: int = 4

# Default Cisco factory credentials, overridable via environment variables
PHONE_SSH_USER: str = os.environ.get("ASTERISK_CLI_PHONE_SSH_USER", "admin")
PHONE_SSH_PASS: str = os.environ.get("ASTERISK_CLI_PHONE_SSH_PASS", "cisco")

# Production paths by default; overridable via ASTERISK_CLI_ETC and
# ASTERISK_CLI_TFTPBOOT in .env
ETC_ASTERISK: Path = Path(os.environ.get("ASTERISK_CLI_ETC", "/etc/asterisk"))
TFTPBOOT: Path = Path(
    os.environ.get("ASTERISK_CLI_TFTPBOOT", "/var/lib/tftpboot")
)

# Required files + paths

SIP_CONF: Path = ETC_ASTERISK / "sip.conf"
EXTENSIONS_CONF: Path = ETC_ASTERISK / "extensions.conf"
VOICEMAIL_CONF: Path = ETC_ASTERISK / "voicemail.conf"
XML_TEMPLATE: Path = TFTPBOOT / "SEP0000000.cnf.xml"
REQUIRED_FILES: tuple[Path, ...] = (
    SIP_CONF,
    EXTENSIONS_CONF,
    VOICEMAIL_CONF,
    XML_TEMPLATE,
)

# Config file names (basename only)
SIP_CONF_NAME: Final[str] = "sip.conf"
EXTENSIONS_CONF_NAME: Final[str] = "extensions.conf"
VOICEMAIL_CONF_NAME: Final[str] = "voicemail.conf"
XML_CONFIG_EXTENSION: Final[str] = ".cnf.xml"

# SIP configuration directives
CALLERID_DIRECTIVE: Final[str] = "callerid="

# Cisco SEP device prefix
SEP_PREFIX: Final[str] = "SEP"

# Voicemail mailbox context
MAILBOX_CONTEXT: Final[str] = "default"

# Search method identifiers
SearchMethod = Literal["ext", "mac", "callerid"]
SEARCH_BY_EXTENSION: Final[SearchMethod] = "ext"
SEARCH_BY_MAC: Final[SearchMethod] = "mac"
SEARCH_BY_CALLER_ID: Final[SearchMethod] = "callerid"


RICH_THEME: Theme = Theme(
    {
        "primary": DRACULA.purple,
        "secondary": DRACULA.comment,
        "accent": DRACULA.pink,
        "info": DRACULA.cyan,
        "success": DRACULA.green,
        "warning": DRACULA.orange,
        "danger": DRACULA.red,
        "muted": DRACULA.comment,
    }
)


@dataclass(frozen=True)
class CallForwardingDefinition:
    """Dataclass to hold call forwarding information for users.

    Attributes:
        name: Name of the user.
        extension: User's internal extension.
        forwarding_number: User's phone number to forward calls to.
    """

    name: str
    extension: str
    forwarding_number: str


CALL_FORWARDING_FILE: Path = Path(
    os.environ.get(
        "ASTERISK_CLI_CALL_FORWARDING_FILE",
        "/etc/asterisk-phone-management/call_forwarding.toml",
    )
)


def load_call_forwarding_users(
    path: Path = CALL_FORWARDING_FILE,
) -> list[CallForwardingDefinition]:
    """Load the call forwarding roster from a TOML file.

    Args:
        path: Path to the roster file.

    Returns:
        The configured users, or an empty list if the file does not exist.
    """
    if not path.exists():
        return []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return [
        CallForwardingDefinition(
            name=user["name"],
            extension=user["extension"],
            forwarding_number=user["forwarding_number"],
        )
        for user in data.get("users", [])
    ]


CALL_FORWARDING_USERS: list[CallForwardingDefinition] = (
    load_call_forwarding_users()
)


_LOG_FORMAT: str = "%(message)s"

console: Console = Console(theme=RICH_THEME)

logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True, markup=True)],
)

log: logging.Logger = logging.getLogger("Asterisk Phone Management")
