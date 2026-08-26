"""Application-wide constants and shared configuration.

This module centralizes constants, required file paths, and logging
configuration used across the Asterisk phone management tool.
"""

import logging
import os
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

MAC_ADDRESS_LENGTH: int = 12
EXTENSION_LENGTH: int = 4
MINIMUM_VM_PASSWORD_LENGTH: int = 4

# Default Cisco factory credentials, overridable via environment variables
PHONE_SSH_USER: str = os.environ.get("ASTERISK_CLI_PHONE_SSH_USER", "admin")
PHONE_SSH_PASS: str = os.environ.get("ASTERISK_CLI_PHONE_SSH_PASS", "cisco")

# Defaults target a local ./config sandbox for development; set
# ASTERISK_CLI_ETC and ASTERISK_CLI_TFTPBOOT to point at the real
# /etc/asterisk and /var/lib/tftpboot in production.
ETC_ASTERISK: Path = Path(
    os.environ.get(
        "ASTERISK_CLI_ETC",
        str(Path(__file__).parent.parent / "config" / "asterisk"),
    )
)
TFTPBOOT: Path = Path(
    os.environ.get(
        "ASTERISK_CLI_TFTPBOOT",
        str(Path(__file__).parent.parent / "config" / "tftpboot"),
    )
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


_LOG_FORMAT: str = "%(message)s"

console: Console = Console()

logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True, markup=True)],
)

log: logging.Logger = logging.getLogger("rich")
