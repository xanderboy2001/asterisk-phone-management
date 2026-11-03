"""Unit tests for call forwarding error handling."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management.core.constants import CallForwardingDefinition
from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    AsteriskServiceError,
    FileTransactionError,
)
from asterisk_phone_management.schemas.models import ConfigMatch
from asterisk_phone_management.services import call_forwarding

USER = CallForwardingDefinition(
    name="Buzz Lightyear", extension="1001", forwarding_number="15555550100"
)
FORWARD = "&SIP/15555550100@cisco_vg"
DISABLED_LINE = f"exten => 1001,1,Dial(SIP/SEP112233445566,14,t);{FORWARD}"


def test_enable_rejects_unexpected_dialplan_format() -> None:
    """A line without Dial(...,...) is reported, not a raw ValueError."""
    with pytest.raises(AsteriskServiceError, match="Unexpected dialplan"):
        call_forwarding._enable_forwarding_text(
            f"exten => 1001,1,Hangup;{FORWARD}", USER
        )


def test_write_config_update_rejects_missing_line(tmp_path: Path) -> None:
    """A line number past the end of the file isn't an IndexError."""
    conf = tmp_path / "extensions.conf"
    conf.write_text("[default]\n", encoding="utf-8")
    match = ConfigMatch(file_path=conf, line_number=5, matched_text="x")
    with pytest.raises(AsteriskCliError, match="no longer exists"):
        call_forwarding._write_config_update(match, "x", "y")
    assert conf.read_text(encoding="utf-8") == "[default]\n"


def test_toggle_wraps_os_errors(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """A read/write failure becomes FileTransactionError, rolled back."""
    ext_conf = mock_asterisk_env["ext_conf"]
    ext_conf.write_text(f"[default]\n{DISABLED_LINE}\n", encoding="utf-8")
    before = ext_conf.read_text(encoding="utf-8")
    mocker.patch.object(
        call_forwarding,
        "get_call_forwarding_config",
        return_value=ConfigMatch(
            file_path=ext_conf, line_number=2, matched_text=DISABLED_LINE
        ),
    )
    mocker.patch.object(
        call_forwarding, "atomic_write_text", side_effect=OSError("disk full")
    )

    with pytest.raises(FileTransactionError, match="disk full"):
        call_forwarding.toggle_call_forwarding(USER, "enable")

    assert ext_conf.read_text(encoding="utf-8") == before


def test_toggle_enables_forwarding(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """Enabling moves the forwarding target inside Dial(...)."""
    ext_conf = mock_asterisk_env["ext_conf"]
    ext_conf.write_text(f"[default]\n{DISABLED_LINE}\n", encoding="utf-8")
    mocker.patch.object(
        call_forwarding,
        "get_call_forwarding_config",
        return_value=ConfigMatch(
            file_path=ext_conf, line_number=2, matched_text=DISABLED_LINE
        ),
    )

    call_forwarding.toggle_call_forwarding(USER, "enable")

    assert f"Dial(SIP/SEP112233445566{FORWARD},14,t)" in ext_conf.read_text(
        encoding="utf-8"
    )
