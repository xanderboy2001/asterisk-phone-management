"""Service functions for modifying caller ID configurations."""

from asterisk_phone_management.core.constants import SIP_CONF, log
from asterisk_phone_management.core.exceptions import (
    FileTransactionError,
)
from asterisk_phone_management.core.transactions import ConfigTransaction
from asterisk_phone_management.schemas.models import ConfigMatch


def _apple_caller_id_updates(
    lines: list[str], target_indicies: list[int], new_caller_id: str
) -> list[str]:
    """Validate target indicies and apply new caller ID values to lines.

    Args:
        lines: Lines of the configuration file.
        target_indicies: Line numbers (0-indexed) to update.
        new_caller_id: The replacement caller ID string.

    Returns:
        Updated list of configuration line strings.

    Raises:
        FileTransactionError: If an index is out of bounds or invalid.
    """
    updated_lines = list(lines)
    for idx in target_indicies:
        if idx < 0 or idx >= len(updated_lines):
            msg = f"Target line number {idx} out of range."
            log.error(msg)
            raise FileTransactionError(msg)

        if not updated_lines[idx].strip().startswith("callerid="):
            msg = f"Line mismatch at index {idx}: expected callerid directive."
            log.error(msg)
            raise FileTransactionError(msg)

        updated_lines[idx] = f"callerid={new_caller_id}"

    return updated_lines


def edit_caller_id(
    target_matches: list[ConfigMatch], new_caller_id: str
) -> None:
    """Update caller ID directive in sip.conf for specified matches.

    Args:
        target_matches: ConfigMatch entries representing lines to update.
        new_caller_id: The new caller ID string.

    Raises:
        FileTransactionError: If file modification or index validation fails.
    """
    target_indicies = [match.line_number - 1 for match in target_matches]
    if not target_indicies:
        return
    try:
        with ConfigTransaction((SIP_CONF,)):
            lines = SIP_CONF.read_text(encoding="utf-8").splitlines()
            updated_lines = _apple_caller_id_updates(
                lines, target_indicies, new_caller_id
            )
            updated_content = "\n".join(updated_lines) + "\n"
            SIP_CONF.write_text(updated_content, encoding="utf-8")
    except OSError as e:
        msg = f"Failed to modify {SIP_CONF}: {e}"
        log.error(msg)
        raise FileTransactionError(msg) from e
