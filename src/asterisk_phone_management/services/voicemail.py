"""Voicemail password management services."""

import re

from asterisk_phone_management.core.constants import (
    VOICEMAIL_CONF_NAME,
    log,
)
from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    FileTransactionError,
)
from asterisk_phone_management.core.settings import get_settings
from asterisk_phone_management.core.transactions import ConfigTransaction
from asterisk_phone_management.core.validators import (
    ensure_valid,
    validate_extension,
    validate_vm_password,
)
from asterisk_phone_management.helpers import atomic_write_text
from asterisk_phone_management.services.search import search_for_extension


def reset_vm_password(extension: str, new_pin: str) -> None:
    """Reset the voicemail password for a given extension.

    Args:
        extension: The extension whose voicemail PIN should be reset.
        new_pin: The new voicemail PIN to write.

    Raises:
        AsteriskCliError: If the extension or PIN is invalid, or no
            voicemail box is found for the extension.
        FileTransactionError: If voicemail.conf could not be updated. The
            file is rolled back to its prior state before this is raised.
    """
    ensure_valid(validate_extension(extension))
    ensure_valid(validate_vm_password(new_pin))
    voicemail_conf = get_settings().voicemail_conf
    extension_matches = search_for_extension(extension)

    voicemail_match = [
        match
        for match in extension_matches
        if match.file_path.name == VOICEMAIL_CONF_NAME
    ]

    if not voicemail_match:
        msg = (
            f"Voicemail box for extension {extension} "
            f"not found in {voicemail_conf.name}."
        )
        log.error(msg)
        raise AsteriskCliError(msg)

    log.info("Voicemail box for extension %s found.", extension)

    try:
        with ConfigTransaction((voicemail_conf,)):
            content = voicemail_conf.read_text(encoding="utf-8")
            pattern = rf"^({re.escape(extension)}\s*=>?\s*)[^,]*"
            updated_content = re.sub(
                pattern=pattern,
                # A function replacement stops the PIN being parsed as a
                # regex template (e.g. backslashes or group references).
                repl=lambda m: m.group(1) + new_pin,
                string=content,
                flags=re.MULTILINE,
            )
            atomic_write_text(voicemail_conf, updated_content)
    except OSError as e:
        msg = f"Failed to modify {voicemail_conf}: {e}"
        log.error(msg)
        raise FileTransactionError(msg) from e

    log.info("Voicemail PIN updated for extension %s.", extension)
