"""Unit tests for system helper functions."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from src.core.exceptions import AsteriskCliError
from src.helpers import (
    backup_config_file,
    copy_file_safe,
    get_ext_from_mac,
    get_mac_from_ext,
)
from src.schemas.models import ConfigMatch


def test_copy_file_safe_success(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
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
    src = tmp_path / "src.txt"
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
    src = tmp_path / "src.txt"
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


def test_backup_config_file_missing_backup_dir(tmp_path: Path) -> None:
    config_file = tmp_path / "sip.conf"
    config_file.write_text("data", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
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
