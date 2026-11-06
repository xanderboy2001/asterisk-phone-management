"""Service functions for modifying caller ID configurations."""

from asterisk_phone_management.core.constants import (
    CALLERID_DIRECTIVE,
    SIP_CONF_NAME,
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
    validate_caller_id,
)
from asterisk_phone_management.helpers import atomic_write_text
from asterisk_phone_management.schemas.models import ConfigMatch


def _check_target_file(match: ConfigMatch) -> None:
    """Refuse a match that doesn't come from sip.conf.

    Args:
        match: A line selected for update.

    Raises:
        AsteriskCliError: If the match points at any other file.
    """
    sip_conf = get_settings().sip_conf
    if match.file_path.resolve() != sip_conf.resolve():
        msg = (
            f"Caller IDs can only be edited in {sip_conf.name}, not "
            f"{match.file_path.name} (line {match.line_number})."
        )
        log.error(msg)
        raise AsteriskCliError(msg)


def _apply_caller_id_updates(
    lines: list[str], target_matches: list[ConfigMatch], new_caller_id: str
) -> list[str]:
    """Replace the caller ID on each matched line, after re-checking it.

    Every line must still read exactly as it did when it was searched.
    If any line doesn't, nothing is changed: sip.conf was edited in the
    meantime and the line numbers can't be trusted.

    Args:
        lines: Current lines of sip.conf.
        target_matches: The lines to update, as found by the search.
        new_caller_id: The replacement caller ID string.

    Returns:
        A new list of lines with the caller IDs replaced. Each line keeps
        its original indentation.

    Raises:
        AsteriskCliError: If a line no longer exists, no longer matches
            the searched text, or isn't a ``callerid=`` line.
    """
    updated_lines = list(lines)
    for match in target_matches:
        idx = match.line_number - 1
        if not 0 <= idx < len(updated_lines):
            msg = (
                f"Line {match.line_number} no longer exists in "
                f"{SIP_CONF_NAME}. The file changed; search again."
            )
            log.error(msg)
            raise AsteriskCliError(msg)

        current = updated_lines[idx]
        expected = match.matched_text.strip()
        if current.strip() != expected:
            msg = (
                f"Line {match.line_number} of {SIP_CONF_NAME} changed since "
                f"the search (expected {expected!r}). Search again."
            )
            log.error(msg)
            raise AsteriskCliError(msg)

        if not expected.startswith(CALLERID_DIRECTIVE):
            msg = (
                f"Line {match.line_number} of {SIP_CONF_NAME} is not a "
                f"{CALLERID_DIRECTIVE} line."
            )
            log.error(msg)
            raise AsteriskCliError(msg)

        indent = current[: len(current) - len(current.lstrip())]
        updated_lines[idx] = f"{indent}{CALLERID_DIRECTIVE}{new_caller_id}"

    return updated_lines


def edit_caller_id(
    target_matches: list[ConfigMatch], new_caller_id: str
) -> None:
    """Update caller ID directive in sip.conf for specified matches.

    Each match must come from sip.conf and its line must still read
    exactly as it did when it was searched. Otherwise nothing is written.

    Args:
        target_matches: ConfigMatch entries representing lines to update.
        new_caller_id: The new caller ID string.

    Raises:
        AsteriskCliError: If the new caller ID is invalid, a match isn't
            from sip.conf, or a matched line changed since the search.
        FileTransactionError: If sip.conf can't be read or written. The
            file is rolled back before this is raised.
    """
    ensure_valid(validate_caller_id(new_caller_id))
    if not target_matches:
        return
    for match in target_matches:
        _check_target_file(match)
    sip_conf = get_settings().sip_conf
    try:
        with ConfigTransaction((sip_conf,)):
            lines = sip_conf.read_text(encoding="utf-8").splitlines()
            updated_lines = _apply_caller_id_updates(
                lines, target_matches, new_caller_id
            )
            atomic_write_text(sip_conf, "\n".join(updated_lines) + "\n")
    except OSError as e:
        msg = f"Failed to modify {sip_conf}: {e}"
        log.error(msg)
        raise FileTransactionError(msg) from e
