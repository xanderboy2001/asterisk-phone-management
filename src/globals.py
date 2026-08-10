"""Hold global variables."""

import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

MAC_ADDRESS_LENGTH: int = 12
EXTENSION_LENGTH: int = 4
# ETC_ASTERISK: Path = Path("/etc/asterisk")
ETC_ASTERISK: Path = Path(Path(__file__).parent.parent / "config/asterisk")
# TFTPBOOT: Path = Path("/var/lib/tftpboot")
TFTPBOOT: Path = Path(Path(__file__).parent.parent / "config/tftpboot")
# Required files + paths
REQUIRED_FILES: dict[str, Path] = {
    "SIP_CONF": ETC_ASTERISK / "sip.conf",
    "EXTENSIONS_CONF": ETC_ASTERISK / "extensions.conf",
    "VOICEMAIL_CONF": ETC_ASTERISK / "voicemail.conf",
    "XML_TEMPLATE": TFTPBOOT / "SEP0000000.cnf.xml",
}


console = Console()
FORMAT = "%(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True, markup=True)],
)

log = logging.getLogger("rich")
