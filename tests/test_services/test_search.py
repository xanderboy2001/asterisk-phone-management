"""Unit tests for configuration file search services."""

from pathlib import Path

import pytest

from asterisk_phone_management.services.search import (
    _is_extensions_ext_match,
    _is_extensions_mac_match,
    _is_sip_ext_match,
    _is_sip_mac_match,
    _is_voicemail_ext_match,
    search_for_extension,
    search_for_mac_address,
)


def test_match_rules() -> None:
    assert _is_sip_ext_match('caller_id="John" <1001>', "1001")
    assert not _is_sip_ext_match('caller_id="John" <1002>', "1001")

    assert _is_extensions_ext_match(
        "exten => 1001,1,Dial(SIP/SEP112233445566)", "1001"
    )
    assert not _is_extensions_ext_match(
        "exten => 1002,1,Dial(SIP/SEP112233445566)", "1001"
    )

    assert _is_voicemail_ext_match("1001 = 1234, John", "1001")
    assert not _is_voicemail_ext_match("1002 = 1234, John", "1001")

    assert _is_sip_mac_match("[SEP112233445566]", "112233445566")
    assert not _is_sip_mac_match("[SEP999999999999]", "112233445566")

    assert _is_extensions_mac_match(
        "exten => 1001,1,Dial(SIP/SEP112233445566)", "112233445566"
    )
    assert not _is_extensions_mac_match(
        "exten => 1001,1,Dial(SIP/SEP999999999999)", "112233445566"
    )


@pytest.mark.usefixtures("mock_asterisk_env")
def test_search_for_extension_found() -> None:
    results = search_for_extension("1001")
    assert len(results) >= 3
    file_names = {match.file_path.name for match in results}
    assert "sip.conf" in file_names
    assert "extensions.conf" in file_names
    assert "voicemail.conf" in file_names


@pytest.mark.usefixtures("mock_asterisk_env")
def test_search_for_extension_not_found() -> None:
    results = search_for_extension("9999")
    assert results == []


@pytest.mark.usefixtures("mock_asterisk_env")
def test_search_for_extension_missing_file_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing_file = tmp_path / "nonexistent.conf"
    monkeypatch.setattr("src.services.search.SIP_CONF", missing_file)
    results = search_for_extension("1001")
    file_names = {match.file_path.name for match in results}
    assert "sip.conf" not in file_names


def test_search_for_extension_read_error(
    mock_asterisk_env: dict[str, Path],
) -> None:
    sip_conf = mock_asterisk_env["sip_conf"]

    # Remove read permissions to natively trigger an OSError/PermissionError
    sip_conf.chmod(0o000)

    try:
        # The application allows the read error to bubble up, so we explicitly test for it
        with pytest.raises(PermissionError):
            search_for_extension("1001")
    finally:
        # Restore permissions so pytest cleanup doesn't fail
        sip_conf.chmod(0o644)


@pytest.mark.usefixtures("mock_asterisk_env")
def test_search_for_mac_address_found() -> None:
    results = search_for_mac_address("112233445566")
    assert len(results) >= 2
    file_names = {match.file_path.name for match in results}
    assert "sip.conf" in file_names
    assert "extensions.conf" in file_names


@pytest.mark.usefixtures("mock_asterisk_env")
def test_search_for_mac_address_not_found() -> None:
    results = search_for_mac_address("000000000000")
    assert results == []


@pytest.mark.usefixtures("mock_asterisk_env")
def test_search_for_mac_address_missing_file_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing_file = tmp_path / "nonexistent.conf"
    monkeypatch.setattr("src.services.search.SIP_CONF", missing_file)
    results = search_for_mac_address("112233445566")
    file_names = {match.file_path.name for match in results}
    assert "sip.conf" not in file_names


def test_search_for_mac_address_read_error(
    mock_asterisk_env: dict[str, Path],
) -> None:
    sip_conf = mock_asterisk_env["sip_conf"]
    sip_conf.chmod(0o000)
    try:
        with pytest.raises(PermissionError):
            search_for_mac_address("112233445566")
    finally:
        sip_conf.chmod(0o644)
