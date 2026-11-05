"""Unit tests for configuration file search services."""

import logging
from pathlib import Path

import pytest

from asterisk_phone_management.services import search as search_module
from asterisk_phone_management.services.search import (
    _is_caller_id_match,
    _is_extensions_ext_match,
    _is_extensions_mac_match,
    _is_sip_ext_match,
    _is_sip_mac_match,
    _is_voicemail_ext_match,
    search_for_caller_id,
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


def test_match_rules_caller_id() -> None:
    assert _is_caller_id_match('callerid="John Doe" <1001>', "John") is True
    assert _is_caller_id_match('callerid="John Doe" <1001>', "Jane") is False
    assert _is_caller_id_match("context=default", "John") is False


@pytest.mark.usefixtures("mock_asterisk_env")
def test_search_for_extension_found() -> None:
    results = search_for_extension("1001")
    assert len(results) >= 3
    file_names = {match.file_path.name for match in results}
    assert "sip.conf" in file_names
    assert "extensions.conf" in file_names
    assert "voicemail.conf" in file_names


def test_search_for_extension_xml_found(
    mock_asterisk_env: dict[str, Path],
) -> None:
    tftpboot: Path = mock_asterisk_env["tftp_dir"]

    # Create a mock XML file with the matching extension pattern
    xml_file: Path = tftpboot / "SEP112233445566.cnf.xml"
    xml_file.write_text(
        "<featureLabel>1001</featureLabel>\n", encoding="utf-8"
    )

    results = search_for_extension("1001")

    # Verify the XML file was successfully scanned and yielded
    file_names = {match.file_path.name for match in results}
    assert "SEP112233445566.cnf.xml" in file_names


@pytest.mark.usefixtures("mock_asterisk_env")
def test_search_for_extension_not_found() -> None:
    results = search_for_extension("9999")
    assert results == []


@pytest.mark.usefixtures("mock_asterisk_env")
def test_search_for_extension_missing_file_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing_file = tmp_path / "nonexistent.conf"
    monkeypatch.setattr(search_module, "SIP_CONF", missing_file)
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
def test_search_for_extension_masks_voicemail_pin_in_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Voicemail PINs are masked in log output but kept in the results."""
    with caplog.at_level(logging.INFO):
        results = search_for_extension("1001")
    assert "1001 = ****, John Doe" in caplog.text
    assert "1001 = 1234" not in caplog.text
    vm_matches = [m for m in results if m.file_path.name == "voicemail.conf"]
    assert vm_matches[0].matched_text.startswith("1001 = 1234")


@pytest.mark.usefixtures("mock_asterisk_env")
def test_search_for_mac_address_found() -> None:
    results = search_for_mac_address("112233445566")
    assert len(results) >= 2
    file_names = {match.file_path.name for match in results}
    assert "sip.conf" in file_names
    assert "extensions.conf" in file_names


def test_search_for_mac_address_xml_found(
    mock_asterisk_env: dict[str, Path],
) -> None:
    tftpboot: Path = mock_asterisk_env["tftp_dir"]

    # Create mock XML file with matching MAC address pattern
    xml_file: Path = tftpboot / "SEP112233445566.cnf.xml"
    xml_file.write_text("<name>SEP112233445566</name>\n", encoding="utf-8")

    results = search_for_mac_address("112233445566")

    # Verify the XML file was successfully scanned and yielded
    file_names = {match.file_path.name for match in results}
    assert "SEP112233445566.cnf.xml" in file_names


@pytest.mark.usefixtures("mock_asterisk_env")
def test_search_for_mac_address_not_found() -> None:
    results = search_for_mac_address("000000000000")
    assert results == []


@pytest.mark.usefixtures("mock_asterisk_env")
def test_search_for_mac_address_missing_file_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing_file = tmp_path / "nonexistent.conf"
    monkeypatch.setattr(search_module, "SIP_CONF", missing_file)
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


@pytest.mark.parametrize(
    "mac", ["112233445566", "11:22:33:44:55:66", "11-22-33-44-55-66"]
)
@pytest.mark.usefixtures("mock_asterisk_env")
def test_search_for_mac_address_accepts_any_format(mac: str) -> None:
    """Separated and lowercase input finds the same files as normalized."""
    file_names = {m.file_path.name for m in search_for_mac_address(mac)}
    assert file_names == {
        "sip.conf",
        "extensions.conf",
        "SEP112233445566.cnf.xml",
    }


def test_search_for_mac_address_matches_lowercase_config(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """Config lines written in lowercase are still found."""
    sip_conf = mock_asterisk_env["sip_conf"]
    sip_conf.write_text("[sepaabbccddeeff](phone)\n", encoding="utf-8")
    results = search_for_mac_address("AABBCCDDEEFF")
    assert [m.file_path.name for m in results] == ["sip.conf"]


def test_mac_match_rules_ignore_case() -> None:
    """Both config matchers compare MAC addresses case-insensitively."""
    assert _is_sip_mac_match("[sepaabbccddeeff](phone)", "AABBCCDDEEFF")
    assert _is_extensions_mac_match(
        "exten => 1001,1,Dial(SIP/sepaabbccddeeff,14,t)", "AABBCCDDEEFF"
    )


def test_search_for_caller_id_found(
    mock_asterisk_env: dict[str, Path],
) -> None:
    sip_conf = mock_asterisk_env["sip_conf"]

    sip_conf.write_text(
        sip_conf.read_text(encoding="utf-8") + 'callerid="Alice" <1002>\n',
        encoding="utf-8",
    )

    results = search_for_caller_id("Alice")

    assert len(results) == 1
    assert results[0].file_path.name == "sip.conf"
    assert 'callerid="Alice"' in results[0].matched_text


@pytest.mark.usefixtures("mock_asterisk_env")
def test_search_for_caller_id_not_found() -> None:
    results = search_for_caller_id("nonexistentUser")
    assert results == []


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("exten => 1001,1,Dial(SIP/SEP1)", True),
        ("exten=>1001,1,Dial(SIP/SEP1)", True),
        ("  exten  =>  1001 ,n,Voicemail(1001,u)", True),
        ("exten => 10012,1,Dial(SIP/SEP1)", False),
        ("exten => 21001,1,Dial(SIP/SEP1)", False),
        ("; exten => 1001,1,Dial(SIP/SEP1)", False),
    ],
)
def test_extensions_ext_match_is_exact(line: str, expected: bool) -> None:
    """Only the exact extension matches, with any spacing (F-13)."""
    assert _is_extensions_ext_match(line, "1001") is expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("1001 = 1234, John", True),
        ("1001 => 1234, John", True),
        ("  1001=1234, John", True),
        ("10012 = 1234, Jane", False),
        (";1001 = 1234, John", False),
        ("[1001]", False),
    ],
)
def test_voicemail_ext_match_is_exact(line: str, expected: bool) -> None:
    """Only the exact mailbox matches; prefixes and comments don't (F-13)."""
    assert _is_voicemail_ext_match(line, "1001") is expected


def test_search_for_extension_ignores_longer_extensions(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """Searching 1001 doesn't return lines that belong to 10012."""
    ext_conf = mock_asterisk_env["ext_conf"]
    vm_conf = mock_asterisk_env["vm_conf"]
    ext_conf.write_text(
        ext_conf.read_text(encoding="utf-8")
        + "exten => 10012,1,Dial(SIP/SEPAABBCCDDEEFF,14,t)\n",
        encoding="utf-8",
    )
    vm_conf.write_text(
        vm_conf.read_text(encoding="utf-8") + "10012 = 9999, Jane, j@x.com\n",
        encoding="utf-8",
    )
    results = search_for_extension("1001")
    assert not any("10012" in m.matched_text for m in results)


def test_search_for_caller_id_strips_matched_text(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """Matched lines are stripped, like every other search."""
    sip_conf = mock_asterisk_env["sip_conf"]
    sip_conf.write_text(
        sip_conf.read_text(encoding="utf-8") + 'callerid="Alice" <1002>   \n',
        encoding="utf-8",
    )

    results = search_for_caller_id("Alice")

    assert [m.matched_text for m in results] == ['callerid="Alice" <1002>']


def test_search_for_caller_id_missing_sip_conf(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A missing sip.conf means no matches, not a crash."""
    monkeypatch.setattr(search_module, "SIP_CONF", tmp_path / "missing.conf")

    assert search_for_caller_id("Alice") == []
