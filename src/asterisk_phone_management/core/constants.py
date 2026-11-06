"""Application-wide constants and shared configuration.

Importing this module does not load configuration or configure logging.
Runtime configuration is provided by core.settings.
"""

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from rich.console import Console
from rich.theme import Theme

from asterisk_phone_management.core.settings import get_settings
from asterisk_phone_management.core.theme import DRACULA

MAC_ADDRESS_LENGTH: int = 12
EXTENSION_LENGTH: int = 4
MINIMUM_VM_PASSWORD_LENGTH: int = 4
MAX_CALLER_ID_LENGTH: int = 80

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


def load_call_forwarding_users(
    path: Path | None = None,
) -> list[CallForwardingDefinition]:
    """Load the call forwarding roster from a TOML file.

    Args:
        path: Path to the roster file.

    Returns:
        The configured users, or an empty list if the file does not exist.
    """
    if path is None:
        path = get_settings().call_forwarding_file
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


console: Console = Console(theme=RICH_THEME)
log: logging.Logger = logging.getLogger("Asterisk Phone Management")
