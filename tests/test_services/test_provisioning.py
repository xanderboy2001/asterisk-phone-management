"""Unit tests for phone provisioning, deprovisioning, and replacement."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    AsteriskServiceError,
)
from asterisk_phone_management.schemas.models import Phone, Voicemail
from asterisk_phone_management.services.provisioning import (
    _cleanup_created_files,
    _deprovision_phone,
    _provision_phone,
    _remove_cnf_xml,
    _replace_mac_in_file,
    register_phone,
    remove_phone,
    replace_phone,
)


def test_remove_cnf_xml_success(tmp_path: Path) -> None:
    target = tmp_path / "SEP112233445566.cnf.xml"
    target.write_text("content", encoding="utf-8")

    _remove_cnf_xml(target)

    assert not target.exists()


def test_remove_cnf_xml_invalid_extension(tmp_path: Path) -> None:
    target = tmp_path / "SEP112233445566.txt"

    with pytest.raises(
        AsteriskCliError, match=r"Provided file is not a .cnf.xml file"
    ):
        _remove_cnf_xml(target)


def test_remove_cnf_xml_permission_error(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    target = tmp_path / "SEP112233445566.cnf.xml"
    target.write_text("content", encoding="utf-8")

    mocker.patch.object(
        Path, "unlink", side_effect=PermissionError("Permission error")
    )

    with pytest.raises(
        AsteriskCliError, match="Invalid permissions to delete"
    ):
        _remove_cnf_xml(target)


def test_remove_cnf_xml_os_error(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    target = tmp_path / "SEP112233445566.cnf.xml"
    target.write_text("content", encoding="utf-8")

    mocker.patch.object(Path, "unlink", side_effect=OSError("OS error"))

    with pytest.raises(AsteriskCliError, match="OS error when deleting"):
        _remove_cnf_xml(target)


def test_provision_phone_flow(
    mock_asterisk_env: dict[str, Path],
    sample_phone: Phone,
    sample_voicemail: Voicemail,
) -> None:
    sip_conf = mock_asterisk_env["sip_conf"]
    ext_conf = mock_asterisk_env["ext_conf"]
    vm_conf = mock_asterisk_env["vm_conf"]
    tftp_dir = mock_asterisk_env["tftp_dir"]

    _provision_phone(sample_phone, sample_voicemail)

    assert f"[SEP{sample_phone.mac_address}]" in sip_conf.read_text(
        encoding="utf-8"
    )
    assert f"exten => {sample_phone.extension}" in ext_conf.read_text(
        encoding="utf-8"
    )
    assert f"{sample_phone.extension} = " in vm_conf.read_text(
        encoding="utf-8"
    )

    created_xml = tftp_dir / f"SEP{sample_phone.mac_address}.cnf.xml"
    assert created_xml.exists()


@pytest.mark.usefixtures("mock_asterisk_env")
def test_provision_phone_error_cleans_up(
    sample_phone: Phone,
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "asterisk_phone_management.services.provisioning._patch_file",
        side_effect=OSError("Disk full"),
    )
    with pytest.raises(
        AsteriskServiceError, match="File system error during registration"
    ):
        _provision_phone(sample_phone, None)


def test_deprovision_phone_flow(mock_asterisk_env: dict[str, Path]) -> None:
    sip_conf = mock_asterisk_env["sip_conf"]
    ext_conf = mock_asterisk_env["ext_conf"]
    vm_conf = mock_asterisk_env["vm_conf"]
    existing_xml = mock_asterisk_env["existing_xml"]

    _deprovision_phone("1001", "112233445566")

    assert "[SEP112233445566]" not in sip_conf.read_text(encoding="utf-8")
    assert "exten => 1001" not in ext_conf.read_text(encoding="utf-8")
    assert "1001 =" not in vm_conf.read_text(encoding="utf-8")
    assert not existing_xml.exists()


@pytest.mark.usefixtures("mock_asterisk_env")
def test_deprovision_phone_os_error(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.services.provisioning._remove_sip_section",
        side_effect=OSError("File system error"),
    )

    with pytest.raises(
        AsteriskServiceError,
        match="File system error during phone deprovisioning",
    ):
        _deprovision_phone("1001", "112233445566")


def test_cleanup_created_files_os_error(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    orphaned_file = tmp_path / "test.xml"
    orphaned_file.write_text("data", encoding="utf-8")
    mocker.patch.object(Path, "unlink", side_effect=OSError("Delete error"))

    _cleanup_created_files([orphaned_file])


def test_replace_mac_in_file_no_matches_warning(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    file_path = tmp_path / "sip.conf"
    file_path.write_text("no matching mac here", encoding="utf-8")
    mock_log = mocker.patch(
        "asterisk_phone_management.services.provisioning.log.warning"
    )

    _replace_mac_in_file(file_path, "112233445566", "AABBCCDDEEFF")
    mock_log.assert_called_once()


@pytest.mark.usefixtures("mock_asterisk_env")
def test_register_phone_success(mocker: MockerFixture) -> None:
    new_phone = Phone(
        extension="9999", mac_address="999999999999", caller_id=""
    )
    mock_confirm = mocker.patch("questionary.confirm")
    mock_confirm.return_value.ask.return_value = True
    mock_provision = mocker.patch(
        "asterisk_phone_management.services.provisioning._provision_phone"
    )
    register_phone(new_phone)
    mock_provision.assert_called_once_with(new_phone, None)


@pytest.mark.usefixtures("mock_asterisk_env")
def test_register_phone_existing_extension(mocker: MockerFixture) -> None:
    existing_phone = Phone(
        extension="1001", mac_address="AABBCCDDEEFF", caller_id=""
    )
    mock_provision = mocker.patch(
        "asterisk_phone_management.services.provisioning._provision_phone"
    )
    register_phone(existing_phone)
    mock_provision.assert_not_called()


@pytest.mark.usefixtures("mock_asterisk_env")
def test_register_phone_existing_mac(mocker: MockerFixture) -> None:
    existing_phone = Phone(
        extension="9999", mac_address="112233445566", caller_id=""
    )
    mock_provision = mocker.patch(
        "asterisk_phone_management.services.provisioning._provision_phone"
    )

    register_phone(existing_phone)
    mock_provision.assert_not_called()


@pytest.mark.usefixtures("mock_asterisk_env")
def test_register_phone_prompt_retry_then_cancel(
    mocker: MockerFixture,
) -> None:
    new_phone = Phone(
        extension="9999", mac_address="999999999999", caller_id=""
    )
    mock_confirm = mocker.patch("questionary.confirm")
    mock_confirm.return_value.ask.side_effect = [None, False]
    mock_provision = mocker.patch(
        "asterisk_phone_management.services.provisioning._provision_phone"
    )

    register_phone(new_phone)
    mock_provision.assert_not_called()


@pytest.mark.usefixtures("mock_asterisk_env")
def test_remove_phone_by_mac_success(mocker: MockerFixture) -> None:
    mock_confirm = mocker.patch("questionary.confirm")
    mock_confirm.return_value.ask.return_value = True
    mock_deprov = mocker.patch(
        "asterisk_phone_management.services.provisioning._deprovision_phone"
    )

    remove_phone("mac", "112233445566")
    mock_deprov.assert_called_once_with("1001", "112233445566")


@pytest.mark.usefixtures("mock_asterisk_env")
def test_remove_phone_ext_not_found() -> None:
    with pytest.raises(
        AsteriskCliError, match="Could not find phone with extension"
    ):
        remove_phone("ext", "9999")


@pytest.mark.usefixtures("mock_asterisk_env")
def test_remove_phone_mac_not_found() -> None:
    with pytest.raises(
        AsteriskCliError, match="Could not find phone with MAC address"
    ):
        remove_phone("mac", "000000000000")


@pytest.mark.usefixtures("mock_asterisk_env")
def test_remove_phone_invalid_method() -> None:
    with pytest.raises(AsteriskCliError, match="Invalid search method"):
        remove_phone("invalid", "1001")


@pytest.mark.usefixtures("mock_asterisk_env")
def test_remove_phone_user_cancels(mocker: MockerFixture) -> None:
    mock_confirm = mocker.patch("questionary.confirm")
    mock_confirm.return_value.ask.return_value = False
    mock_deprov = mocker.patch(
        "asterisk_phone_management.services.provisioning._deprovision_phone"
    )

    remove_phone("ext", "1001")

    mock_deprov.assert_not_called()


@pytest.mark.usefixtures("mock_asterisk_env")
def test_replace_phone_by_ext_success(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.services.provisioning.read_mac_addr",
        return_value="AABBCCDDEEFF",
    )
    mock_generate = mocker.patch(
        "asterisk_phone_management.services.provisioning._generate_cnf_xml"
    )
    replace_phone("ext", "1001")
    mock_generate.assert_called_once_with(
        extension="1001", mac_address="AABBCCDDEEFF"
    )


@pytest.mark.usefixtures("mock_asterisk_env")
def test_replace_phone_by_mac_success(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.services.provisioning.read_mac_addr",
        return_value="AABBCCDDEEFF",
    )
    replace_phone("mac", "112233445566")


@pytest.mark.usefixtures("mock_asterisk_env")
def test_replace_phone_invalid_method() -> None:
    with pytest.raises(AsteriskCliError, match="No option selected"):
        replace_phone("invalid", "1001")


@pytest.mark.usefixtures("mock_asterisk_env")
def test_replace_phone_duplicate_mac_error(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.services.provisioning.read_mac_addr",
        return_value="112233445566",
    )

    with pytest.raises(
        AsteriskServiceError, match=r"Phone with MAC address .* already exists"
    ):
        replace_phone("ext", "1001")


@pytest.mark.usefixtures("mock_asterisk_env")
def test_replace_phone_no_old_cnf_file_warning(
    mocker: MockerFixture, mock_asterisk_env: dict[str, Path]
) -> None:
    mock_asterisk_env["existing_xml"].unlink()
    mocker.patch(
        "asterisk_phone_management.services.provisioning.read_mac_addr",
        return_value="AABBCCDDEEFF",
    )
    mock_log = mocker.patch(
        "asterisk_phone_management.services.provisioning.log.warning"
    )

    replace_phone("ext", "1001")
    mock_log.assert_called()


@pytest.mark.usefixtures("mock_asterisk_env")
def test_replace_phone_os_error_handling(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.services.provisioning.read_mac_addr",
        return_value="AABBCCDDEEFF",
    )
    mocker.patch(
        "asterisk_phone_management.services.provisioning._replace_mac_in_file",
        side_effect=OSError("Write failed"),
    )

    with pytest.raises(
        AsteriskServiceError,
        match="File system error while replacing MAC address",
    ):
        replace_phone("ext", "1001")
