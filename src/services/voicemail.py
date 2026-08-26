"""Voicemail password management services."""

import re

from src.core.exceptions import AsteriskCliError, FileTransactionError
from src.core.globals import VOICEMAIL_CONF, log
from src.core.transactions import ConfigTransaction
from src.services.search import search_for_extension


def reset_vm_password(extension: str, new_pin: str) -> None:
    """Reset the voicemail password for a given extension.

    Args:
        extension: The extension whose voicemail PIN should be reset.
        new_pin: The new voicemail PIN to write.

    Raises:
        AsteriskCliError: If no voicemail box is found for the extension.
        FileTransactionError: If voicemail.conf could not be updated. The
            file is rolled back to its prior state before this is raised.
    """
    extension_matches = search_for_extension(extension)

    voicemail_match = [
        match
        for match in extension_matches
        if match.file_path.name == "voicemail.conf"
    ]

    if not voicemail_match:
        msg = (
            f"Voicemail box for extension {extension} "
            f"not found in {VOICEMAIL_CONF.name}."
        )
        log.error(msg)
        raise AsteriskCliError(msg)

    log.info("Voicemail box for extension %s found.", extension)

    try:
        with ConfigTransaction((VOICEMAIL_CONF,)):
            content = VOICEMAIL_CONF.read_text(encoding="utf-8")
            pattern = rf"^({re.escape(extension)}\s*=>?\s*)[^,]*"
            updated_content = re.sub(
                pattern=pattern,
                repl=rf"\g<1>{new_pin}",
                string=content,
                flags=re.MULTILINE,
            )
            VOICEMAIL_CONF.write_text(updated_content, encoding="utf-8")
    except OSError as e:
        msg = f"Failed to modify {VOICEMAIL_CONF}: {e}"
        log.error(msg)
        raise FileTransactionError(msg) from e

    log.info("Voicemail PIN updated for extension %s.", extension)
