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
from asterisk_phone_management.core.settings import get_settings
from asterisk_phone_management.schemas.models import ConfigMatch
from asterisk_phone_management.services import call_forwarding

USER = CallForwardingDefinition(
    name="Buzz Lightyear", extension="1001", forwarding_number="15555550100"
)
FORWARD = "&SIP/15555550100@cisco_vg"
DISABLED_LINE = f"exten => 1001,1,Dial(SIP/SEP112233445566,14,t);{FORWARD}"

GATEWAY = "cisco_vg"


@pytest.fixture(autouse=True)
def gateway(monkeypatch: pytest.MonkeyPatch) -> str:
    """Configure the forwarding gateway for every test in this file.

    Returns:
        The gateway name in use.
    """
    monkeypatch.setenv("ASTERISK_CLI_FORWARDING_GATEWAY", GATEWAY)
    get_settings.cache_clear()
    return GATEWAY


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


def test_custom_gateway_is_used(
    mock_asterisk_env: dict[str, Path],
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gateway comes from the setting, not a hard-coded name."""
    monkeypatch.setenv("ASTERISK_CLI_FORWARDING_GATEWAY", "test_gw")
    get_settings.cache_clear()
    forward = "&SIP/15555550100@test_gw"
    line = f"exten => 1001,1,Dial(SIP/SEP112233445566,14,t);{forward}"
    ext_conf = mock_asterisk_env["ext_conf"]
    ext_conf.write_text(f"[default]\n{line}\n", encoding="utf-8")
    mocker.patch.object(
        call_forwarding,
        "get_call_forwarding_config",
        return_value=ConfigMatch(
            file_path=ext_conf, line_number=2, matched_text=line
        ),
    )

    call_forwarding.toggle_call_forwarding(USER, "enable")

    assert f"Dial(SIP/SEP112233445566{forward},14,t)" in ext_conf.read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("value", ["", "   "])
def test_unset_gateway_is_refused(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Without a gateway, forwarding stops with a message naming the setting."""
    monkeypatch.setenv("ASTERISK_CLI_FORWARDING_GATEWAY", value)
    get_settings.cache_clear()

    with pytest.raises(
        AsteriskCliError, match="ASTERISK_CLI_FORWARDING_GATEWAY"
    ):
        call_forwarding._build_forwarding_string(USER)


@pytest.mark.parametrize("value", ["cisco_vg\n", "  cisco_vg  "])
def test_gateway_whitespace_is_stripped(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Stray whitespace from .env is removed before the value is used."""
    monkeypatch.setenv("ASTERISK_CLI_FORWARDING_GATEWAY", value)
    get_settings.cache_clear()

    assert (
        call_forwarding._build_forwarding_string(USER)
        == "&SIP/15555550100@cisco_vg"
    )


@pytest.mark.parametrize(
    "value", ["cisco\nvg", "gw,1", "gw;x", "gw)", "gw&SIP/x", "my gw"]
)
def test_unsafe_gateway_is_refused(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Characters that could break the Dial() line are rejected."""
    monkeypatch.setenv("ASTERISK_CLI_FORWARDING_GATEWAY", value)
    get_settings.cache_clear()

    with pytest.raises(AsteriskCliError, match="may only contain"):
        call_forwarding._build_forwarding_string(USER)


def test_unset_gateway_changes_nothing(
    mock_asterisk_env: dict[str, Path],
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing setting fails before extensions.conf is touched."""
    monkeypatch.setenv("ASTERISK_CLI_FORWARDING_GATEWAY", "")
    get_settings.cache_clear()
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

    with pytest.raises(AsteriskCliError):
        call_forwarding.toggle_call_forwarding(USER, "enable")

    assert ext_conf.read_text(encoding="utf-8") == before


def test_mismatched_gateway_is_reported(
    mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A gateway that isn't in the line is an error, not 'enabled'."""
    monkeypatch.setenv("ASTERISK_CLI_FORWARDING_GATEWAY", "other_gw")
    get_settings.cache_clear()
    mocker.patch.object(
        call_forwarding,
        "get_call_forwarding_config",
        return_value=ConfigMatch(
            file_path=Path("extensions.conf"),
            line_number=2,
            matched_text=DISABLED_LINE,
        ),
    )

    with pytest.raises(AsteriskServiceError, match="Check that"):
        call_forwarding.forwarding_enabled(USER)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (DISABLED_LINE, False),
        (f"exten => 1001,1,Dial(SIP/SEP112233445566{FORWARD},14,t)", True),
    ],
)
def test_forwarding_enabled_reads_state(
    mocker: MockerFixture, line: str, expected: bool
) -> None:
    """Both states are read correctly with the configured gateway."""
    mocker.patch.object(
        call_forwarding,
        "get_call_forwarding_config",
        return_value=ConfigMatch(
            file_path=Path("extensions.conf"), line_number=2, matched_text=line
        ),
    )

    assert call_forwarding.forwarding_enabled(USER) is expected
