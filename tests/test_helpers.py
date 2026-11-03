"""Unit tests for system helper functions."""

import os
import re
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management import helpers
from asterisk_phone_management.core.constants import CallForwardingDefinition
from asterisk_phone_management.core.exceptions import AsteriskCliError
from asterisk_phone_management.helpers import (
    atomic_write_bytes,
    atomic_write_text,
    backup_config_file,
    copy_file_safe,
    get_call_forwarding_config,
    get_caller_id_from_ext,
    get_ext_from_mac,
    get_mac_from_ext,
)
from asterisk_phone_management.schemas.models import ConfigMatch

FORWARD_USER = CallForwardingDefinition(
    name="Buzz Lightyear", extension="1001", forwarding_number="15555550100"
)


@pytest.fixture
def forwarding_conf(
    mock_asterisk_env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Point helpers at the test extensions.conf.

    Returns:
        The test extensions.conf path.
    """
    ext_conf = mock_asterisk_env["ext_conf"]
    monkeypatch.setattr(helpers, "EXTENSIONS_CONF", ext_conf)
    return ext_conf


def test_get_call_forwarding_config_found(forwarding_conf: Path) -> None:
    """The single line containing the forwarding number is returned."""
    forwarding_conf.write_text(
        "[default]\n"
        "exten => 1001,1,Dial(SIP/SEP112233445566,14,t)"
        ";&SIP/15555550100@cisco_vg\n",
        encoding="utf-8",
    )
    match = get_call_forwarding_config(FORWARD_USER)
    assert match.line_number == 2
    assert "15555550100" in match.matched_text


@pytest.mark.usefixtures("forwarding_conf")
def test_get_call_forwarding_config_not_found() -> None:
    """No line with the forwarding number raises."""
    with pytest.raises(AsteriskCliError, match="Could not find any matches"):
        get_call_forwarding_config(FORWARD_USER)


def test_get_call_forwarding_config_multiple(
    forwarding_conf: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """More than one candidate line raises and logs each one."""
    line = "exten => 1001,1,Dial(SIP/SEP1,14,t);&SIP/15555550100@cisco_vg\n"
    forwarding_conf.write_text("[default]\n" + line + line, encoding="utf-8")
    with pytest.raises(AsteriskCliError, match="Multiple matches found"):
        get_call_forwarding_config(FORWARD_USER)
    assert caplog.text.count("15555550100") >= 2


def test_copy_file_safe_success(tmp_path: Path) -> None:
    src = tmp_path / "asterisk_phone_management.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("test content", encoding="utf-8")

    copy_file_safe(src, dst)

    assert dst.exists()
    assert dst.read_text(encoding="utf-8") == "test content"


def test_copy_file_safe_file_not_found(tmp_path: Path) -> None:
    src = tmp_path / "missing.txt"
    dst = tmp_path / "dst.txt"

    with pytest.raises(
        AsteriskCliError, match=r"Source file .* does not exist"
    ):
        copy_file_safe(src, dst)


def test_copy_file_safe_same_file(tmp_path: Path) -> None:
    src = tmp_path / "same.txt"
    src.write_text("test content", encoding="utf-8")

    with pytest.raises(
        AsteriskCliError, match="Source and destination paths point"
    ):
        copy_file_safe(src, src)


def test_copy_file_safe_permission_error(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    src = tmp_path / "asterisk_phone_management.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("test_content", encoding="utf-8")

    mocker.patch(
        "shutil.copyfile", side_effect=PermissionError("Permission denied")
    )

    with pytest.raises(
        AsteriskCliError, match="Permission denied accessing source"
    ):
        copy_file_safe(src, dst)


def test_copy_file_safe_os_error(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    src = tmp_path / "asterisk_phone_management.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("test_content", encoding="utf-8")

    mocker.patch("shutil.copyfile", side_effect=OSError("System error"))

    with pytest.raises(
        AsteriskCliError, match="System error during file copy"
    ):
        copy_file_safe(src, dst)


def test_backup_config_file_success(
    mock_asterisk_env: dict[str, Path],
) -> None:
    sip_conf = mock_asterisk_env["sip_conf"]
    backup_dir = mock_asterisk_env["backup_dir"]

    backup_path = backup_config_file(sip_conf)

    assert backup_path.exists()
    assert backup_path.parent == backup_dir
    assert backup_path.name.startswith("sip.conf_")


def test_backup_config_file_permission_error(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    config_file = tmp_path / "sip.conf"
    config_file.write_text("data", encoding="utf-8")
    mocker.patch.object(
        Path, "mkdir", side_effect=PermissionError("Permission denied")
    )

    with pytest.raises(
        AsteriskCliError, match="Permission denied creating backup directory"
    ):
        backup_config_file(config_file)


def test_get_mac_from_ext_success(mock_asterisk_env: dict[str, Path]) -> None:
    ext_match = ConfigMatch(
        file_path=mock_asterisk_env["ext_conf"],
        line_number=1,
        matched_text="exten => 1001,1,Dial(SIP/SEP112233445566,14,t)",
    )
    sip_match = ConfigMatch(
        file_path=mock_asterisk_env["sip_conf"],
        line_number=1,
        matched_text="[SEP112233445566](phone)",
    )
    xml_match = ConfigMatch(
        file_path=mock_asterisk_env["existing_xml"],
        line_number=1,
        matched_text="<featureLabel>1001</featureLabel>",
    )

    assert get_mac_from_ext([ext_match]) == "112233445566"
    assert get_mac_from_ext([sip_match]) == "112233445566"
    assert get_mac_from_ext([xml_match]) == "112233445566"


def test_get_mac_from_ext_failure(tmp_path: Path) -> None:
    invalid_match = ConfigMatch(
        file_path=tmp_path / "sip.conf",
        line_number=1,
        matched_text="no mac here",
    )
    with pytest.raises(
        AsteriskCliError, match="Could not determine MAC address"
    ):
        get_mac_from_ext([invalid_match])


def test_get_ext_from_mac_success(mock_asterisk_env: dict[str, Path]) -> None:
    xml_match = ConfigMatch(
        file_path=mock_asterisk_env["existing_xml"],
        line_number=1,
        matched_text="<name>SEP112233445566</name>",
    )
    ext_match = ConfigMatch(
        file_path=mock_asterisk_env["ext_conf"],
        line_number=1,
        matched_text="exten => 1001,1,Dial(SIP/SEP112233445566,14,t)",
    )

    assert get_ext_from_mac([xml_match]) == "1001"
    assert get_ext_from_mac([ext_match]) == "1001"


def test_get_ext_from_mac_failure(tmp_path: Path) -> None:
    invalid_match = ConfigMatch(
        file_path=tmp_path / "extensions.conf",
        line_number=1,
        matched_text="no exten here",
    )
    with pytest.raises(
        AsteriskCliError, match="Could not determine extension"
    ):
        get_ext_from_mac([invalid_match])


def test_get_caller_id_from_ext_success(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """Test get_caller_id_from_ext extracts caller ID from sip.conf."""
    sip_conf = mock_asterisk_env["sip_conf"]
    sip_conf.write_text(
        '[general]\n[SEP112233445566](phone)\ncallerid="John Doe" <1001>\n',
        encoding="utf-8",
    )
    match = ConfigMatch(
        file_path=sip_conf,
        line_number=4,
        matched_text='callerid="John Doe" <1001>',
    )
    result = get_caller_id_from_ext([match])
    assert result == '"John Doe" <1001>'


def test_get_caller_id_from_ext_failure(tmp_path: Path) -> None:
    """Test get_caller_id_from_ext raises when no caller ID directive found."""
    invalid_match = ConfigMatch(
        file_path=tmp_path / "sip.conf",
        line_number=1,
        matched_text="[general]",
    )
    with pytest.raises(
        AsteriskCliError, match="Could not determine caller ID"
    ):
        get_caller_id_from_ext([invalid_match])


def test_get_ext_from_mac_ignores_longer_extension(tmp_path: Path) -> None:
    """A five-digit extension isn't cut down to its first four digits."""
    match = ConfigMatch(
        file_path=tmp_path / "extensions.conf",
        line_number=1,
        matched_text="exten => 10012,1,Dial(SIP/SEP112233445566,14,t)",
    )
    with pytest.raises(
        AsteriskCliError, match="Could not determine extension"
    ):
        get_ext_from_mac([match])


def _temp_files(directory: Path) -> list[Path]:
    """Return leftover atomic-write temp files in a directory.

    Args:
        directory: The directory to check.

    Returns:
        Any hidden ``.tmp`` files left behind.
    """
    return list(directory.glob(".*.tmp"))


def test_atomic_write_text_replaces_contents(tmp_path: Path) -> None:
    """The file ends up with exactly the new contents."""
    target = tmp_path / "sip.conf"
    target.write_text("old\n", encoding="utf-8")

    atomic_write_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "new\n"


def test_atomic_write_text_keeps_permissions(tmp_path: Path) -> None:
    """The replaced file keeps the original file's mode."""
    target = tmp_path / "sip.conf"
    target.write_text("old\n", encoding="utf-8")
    target.chmod(0o640)

    atomic_write_text(target, "new\n")

    assert target.stat().st_mode & 0o777 == 0o640


def test_atomic_write_text_keeps_owner(tmp_path: Path) -> None:
    """The replaced file keeps the original file's owner and group."""
    target = tmp_path / "sip.conf"
    target.write_text("old\n", encoding="utf-8")
    before = target.stat()

    atomic_write_text(target, "new\n")

    after = target.stat()
    assert (after.st_uid, after.st_gid) == (before.st_uid, before.st_gid)


def test_atomic_write_text_leaves_no_temp_file(tmp_path: Path) -> None:
    """A successful write cleans up after itself."""
    target = tmp_path / "sip.conf"
    target.write_text("old\n", encoding="utf-8")

    atomic_write_text(target, "new\n")

    assert _temp_files(tmp_path) == []


def test_atomic_write_text_failed_rename_keeps_original(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """A failed rename leaves the original and no temp file."""
    target = tmp_path / "sip.conf"
    target.write_text("old\n", encoding="utf-8")
    mocker.patch.object(Path, "replace", side_effect=OSError("disk full"))

    with pytest.raises(OSError, match="disk full"):
        atomic_write_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "old\n"
    assert _temp_files(tmp_path) == []


def test_atomic_write_text_failed_write_keeps_original(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """A failed flush to disk leaves the original and no temp file."""
    target = tmp_path / "sip.conf"
    target.write_text("old\n", encoding="utf-8")
    mocker.patch(
        "asterisk_phone_management.helpers.os.fsync",
        side_effect=OSError("I/O error"),
    )

    with pytest.raises(OSError, match="I/O error"):
        atomic_write_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "old\n"
    assert _temp_files(tmp_path) == []


def test_atomic_write_text_failed_chown_keeps_original(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """If the owner can't be copied, nothing is replaced."""
    target = tmp_path / "sip.conf"
    target.write_text("old\n", encoding="utf-8")
    mocker.patch(
        "asterisk_phone_management.helpers.os.chown",
        side_effect=PermissionError("not root"),
    )

    with pytest.raises(PermissionError, match="not root"):
        atomic_write_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "old\n"
    assert _temp_files(tmp_path) == []


def test_atomic_write_text_cleans_up_on_ctrl_c(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """Ctrl+C mid-write still removes the temp file."""
    target = tmp_path / "sip.conf"
    target.write_text("old\n", encoding="utf-8")
    mocker.patch.object(Path, "replace", side_effect=KeyboardInterrupt)

    with pytest.raises(KeyboardInterrupt):
        atomic_write_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "old\n"
    assert _temp_files(tmp_path) == []


def test_atomic_write_text_follows_symlink(tmp_path: Path) -> None:
    """Writing through a symlink updates the real file and keeps the link."""
    real = tmp_path / "real.conf"
    real.write_text("old\n", encoding="utf-8")
    link = tmp_path / "link.conf"
    link.symlink_to(real)

    atomic_write_text(link, "new\n")

    assert link.is_symlink()
    assert real.read_text(encoding="utf-8") == "new\n"


def test_atomic_write_text_readers_never_see_partial_file(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """Until the rename, the original file still has its full contents."""
    target = tmp_path / "sip.conf"
    target.write_text("old\n", encoding="utf-8")
    seen: list[str] = []
    real_replace = Path.replace

    def _check_then_replace(self: Path, other: Path) -> Path:
        seen.append(target.read_text(encoding="utf-8"))
        return real_replace(self, other)

    mocker.patch.object(Path, "replace", _check_then_replace)

    atomic_write_text(target, "new\n")

    assert seen == ["old\n"]
    assert target.read_text(encoding="utf-8") == "new\n"


def test_atomic_write_bytes_writes_exact_bytes(tmp_path: Path) -> None:
    """Bytes are written unchanged, including CRLF and non-UTF-8 data."""
    target = tmp_path / "sip.conf"
    target.write_text("old\n", encoding="utf-8")

    atomic_write_bytes(target, b"a\r\n\xe9\n")

    assert target.read_bytes() == b"a\r\n\xe9\n"
    assert list(tmp_path.glob(".*.tmp")) == []


@pytest.mark.parametrize(
    "lookup", [get_mac_from_ext, get_ext_from_mac], ids=["mac", "ext"]
)
def test_lookup_from_malformed_xml(
    tmp_path: Path, lookup: Callable[[list[ConfigMatch]], str]
) -> None:
    """A broken .cnf.xml raises AsteriskCliError naming the file."""
    xml = tmp_path / "SEP112233445566.cnf.xml"
    xml.write_text("<device><name>SEP1122", encoding="utf-8")
    match = ConfigMatch(file_path=xml, line_number=1, matched_text="")
    with pytest.raises(AsteriskCliError, match=r"SEP112233445566\.cnf\.xml"):
        lookup([match])


def test_lookup_from_unreadable_xml(tmp_path: Path) -> None:
    """A .cnf.xml that disappeared after the search is reported clearly."""
    match = ConfigMatch(
        file_path=tmp_path / "SEP112233445566.cnf.xml",
        line_number=1,
        matched_text="",
    )
    with pytest.raises(AsteriskCliError, match="Could not read phone config"):
        get_mac_from_ext([match])


# --- F-11: backups are owner-only ---


@pytest.fixture
def open_umask() -> Generator[None]:
    """Run with the common server umask 022, then restore the old one.

    Yields:
        None.
    """
    old = os.umask(0o022)
    try:
        yield
    finally:
        os.umask(old)


@pytest.mark.usefixtures("open_umask")
def test_backup_is_owner_only(tmp_path: Path) -> None:
    """A new backup and its directory are readable only by the owner."""
    conf = tmp_path / "voicemail.conf"
    conf.write_bytes(b"1001 => 1234,John\n")
    conf.chmod(0o640)

    backup = backup_config_file(conf)

    assert backup.stat().st_mode & 0o777 == 0o600
    assert backup.parent.stat().st_mode & 0o777 == 0o700
    assert backup.read_bytes() == conf.read_bytes()


@pytest.mark.usefixtures("open_umask")
def test_backup_tightens_existing_directory(tmp_path: Path) -> None:
    """An existing world-readable backup directory is restricted."""
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    backup_dir.chmod(0o755)
    old_backup = backup_dir / "sip.conf_old"
    old_backup.write_text("secret=old\n", encoding="utf-8")
    conf = tmp_path / "sip.conf"
    conf.write_text("secret=new\n", encoding="utf-8")

    backup_config_file(conf)

    assert backup_dir.stat().st_mode & 0o777 == 0o700


def test_backup_name_includes_microseconds(tmp_path: Path) -> None:
    """Backups made in the same second get different names."""
    conf = tmp_path / "sip.conf"
    conf.write_text("x\n", encoding="utf-8")

    backup = backup_config_file(conf)

    assert re.fullmatch(
        r"sip\.conf_\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2}\.\d{6}", backup.name
    )


def test_backup_never_overwrites(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """If a backup name is already taken, the old backup is kept."""
    conf = tmp_path / "sip.conf"
    conf.write_text("new\n", encoding="utf-8")
    fixed = datetime(2026, 1, 1, 12, 0, 0, 123456, tzinfo=UTC)
    fake_datetime = mocker.patch.object(helpers, "datetime")
    fake_datetime.now.return_value = fixed
    first = backup_config_file(conf)
    first.write_text("original backup\n", encoding="utf-8")

    with pytest.raises(AsteriskCliError, match="already exists"):
        backup_config_file(conf)

    assert first.read_text(encoding="utf-8") == "original backup\n"


def test_backup_missing_source_leaves_nothing(tmp_path: Path) -> None:
    """A missing source raises and leaves no empty backup behind."""
    with pytest.raises(AsteriskCliError, match="file not found"):
        backup_config_file(tmp_path / "missing.conf")

    assert list((tmp_path / "backup").iterdir()) == []


def test_backup_failed_copy_leaves_nothing(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """A copy that fails partway removes the partial backup."""
    conf = tmp_path / "sip.conf"
    conf.write_text("x\n", encoding="utf-8")
    mocker.patch.object(
        helpers.shutil, "copyfileobj", side_effect=OSError("disk full")
    )

    with pytest.raises(AsteriskCliError, match="disk full"):
        backup_config_file(conf)

    assert list((tmp_path / "backup").iterdir()) == []
