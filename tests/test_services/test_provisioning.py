"""Unit tests for phone provisioning, deprovisioning, and replacement."""

import logging
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    AsteriskServiceError,
    FileTransactionError,
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


def test_provision_phone_does_not_log_secrets(
    mock_asterisk_env: dict[str, Path],
    sample_phone: Phone,
    sample_voicemail: Voicemail,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Debug logs never contain the SIP secret or voicemail details."""
    del mock_asterisk_env
    with caplog.at_level(logging.DEBUG):
        _provision_phone(sample_phone, sample_voicemail)
    assert "secret=" not in caplog.text
    assert sample_voicemail.email not in caplog.text


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
def test_register_phone_ctrl_c_cancels(mocker: MockerFixture) -> None:
    """Ctrl+C at the confirmation cancels instead of re-prompting (F-14)."""
    new_phone = Phone(
        extension="9999", mac_address="999999999999", caller_id=""
    )
    mock_confirm = mocker.patch("questionary.confirm")
    mock_confirm.return_value.ask.return_value = None
    mock_provision = mocker.patch(
        "asterisk_phone_management.services.provisioning._provision_phone"
    )

    with pytest.raises(KeyboardInterrupt):
        register_phone(new_phone)
    mock_provision.assert_not_called()
    mock_confirm.assert_called_once()


@pytest.mark.usefixtures("mock_asterisk_env")
def test_register_phone_user_declines(mocker: MockerFixture) -> None:
    """Answering No at the confirmation does not provision."""
    new_phone = Phone(
        extension="9999", mac_address="999999999999", caller_id=""
    )
    mocker.patch("questionary.confirm").return_value.ask.return_value = False
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


# --- replace_phone (F-09): the old phone survives every failure ---

OLD_MAC = "112233445566"
NEW_MAC = "AABBCCDDEEFF"
PROVISIONING = "asterisk_phone_management.services.provisioning"


def _new_xml(env: dict[str, Path]) -> Path:
    """Return where the replacement phone's .cnf.xml would be created.

    Args:
        env: The ``mock_asterisk_env`` fixture.

    Returns:
        The path of the new phone's ``.cnf.xml``.
    """
    return env["tftp_dir"] / f"SEP{NEW_MAC}.cnf.xml"


def _snapshot(env: dict[str, Path]) -> tuple[str, str]:
    """Read both config files so a test can check they are unchanged.

    Args:
        env: The ``mock_asterisk_env`` fixture.

    Returns:
        The contents of sip.conf and extensions.conf.
    """
    return (
        env["sip_conf"].read_text(encoding="utf-8"),
        env["ext_conf"].read_text(encoding="utf-8"),
    )


def _assert_untouched(env: dict[str, Path], before: tuple[str, str]) -> None:
    """Assert the old phone is intact and no new file was left behind.

    Args:
        env: The ``mock_asterisk_env`` fixture.
        before: Config contents captured before the call.
    """
    assert env["existing_xml"].exists()
    assert not _new_xml(env).exists()
    assert _snapshot(env) == before


@pytest.mark.parametrize(
    ("method", "key"), [("ext", "1001"), ("mac", OLD_MAC)]
)
def test_replace_phone_success(
    mock_asterisk_env: dict[str, Path],
    mocker: MockerFixture,
    method: str,
    key: str,
) -> None:
    """The new XML exists, both configs use the new MAC, the old XML is gone."""
    mocker.patch(f"{PROVISIONING}.read_mac_addr", return_value=NEW_MAC)

    replace_phone(method, key)

    sip, ext = _snapshot(mock_asterisk_env)
    assert f"[SEP{NEW_MAC}]" in sip
    assert OLD_MAC not in sip
    assert f"SIP/SEP{NEW_MAC}" in ext
    assert OLD_MAC not in ext
    new_xml = _new_xml(mock_asterisk_env)
    assert new_xml.exists()
    assert "<featureLabel>1001</featureLabel>" in new_xml.read_text(
        encoding="utf-8"
    )
    assert not mock_asterisk_env["existing_xml"].exists()


def test_replace_phone_cancel_at_prompt(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """Ctrl+C at the MAC prompt changes nothing."""
    before = _snapshot(mock_asterisk_env)
    mocker.patch(
        f"{PROVISIONING}.read_mac_addr", side_effect=KeyboardInterrupt
    )
    with pytest.raises(KeyboardInterrupt):
        replace_phone("ext", "1001")
    _assert_untouched(mock_asterisk_env, before)


def test_replace_phone_same_mac(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """Entering the current MAC (any case) is rejected with a clear message."""
    before = _snapshot(mock_asterisk_env)
    mocker.patch(f"{PROVISIONING}.read_mac_addr", return_value=OLD_MAC.lower())
    with pytest.raises(AsteriskCliError, match="matches the current one"):
        replace_phone("ext", "1001")
    assert mock_asterisk_env["existing_xml"].exists()
    assert _snapshot(mock_asterisk_env) == before


def test_replace_phone_duplicate_mac(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """A MAC used by another phone is rejected before anything changes."""
    sip = mock_asterisk_env["sip_conf"]
    sip.write_text(
        sip.read_text(encoding="utf-8") + f"\n[SEP{NEW_MAC}](phone)\n",
        encoding="utf-8",
    )
    before = _snapshot(mock_asterisk_env)
    mocker.patch(f"{PROVISIONING}.read_mac_addr", return_value=NEW_MAC)
    with pytest.raises(AsteriskServiceError, match="already exists"):
        replace_phone("ext", "1001")
    _assert_untouched(mock_asterisk_env, before)


def test_replace_phone_template_missing(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """A copy failure is wrapped as AsteriskServiceError; nothing changes."""
    mock_asterisk_env["xml_template"].unlink()
    before = _snapshot(mock_asterisk_env)
    mocker.patch(f"{PROVISIONING}.read_mac_addr", return_value=NEW_MAC)
    with pytest.raises(AsteriskServiceError, match="replacing MAC address"):
        replace_phone("ext", "1001")
    _assert_untouched(mock_asterisk_env, before)


def test_replace_phone_partial_xml_is_removed(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """A half-written new XML (copied, then patching fails) is cleaned up."""
    before = _snapshot(mock_asterisk_env)
    mocker.patch(f"{PROVISIONING}.read_mac_addr", return_value=NEW_MAC)
    mocker.patch(
        f"{PROVISIONING}._patch_cnf_xml", side_effect=OSError("disk full")
    )
    with pytest.raises(AsteriskServiceError):
        replace_phone("ext", "1001")
    _assert_untouched(mock_asterisk_env, before)


def test_replace_phone_config_edit_fails(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """A failed MAC swap rolls configs back and removes the new XML."""
    before = _snapshot(mock_asterisk_env)
    mocker.patch(f"{PROVISIONING}.read_mac_addr", return_value=NEW_MAC)
    mocker.patch(
        f"{PROVISIONING}._replace_mac_in_file",
        side_effect=OSError("Write failed"),
    )
    with pytest.raises(AsteriskServiceError, match="Write failed"):
        replace_phone("ext", "1001")
    _assert_untouched(mock_asterisk_env, before)


def test_replace_phone_backup_fails(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """A backup failure at transaction start still removes the new XML."""
    before = _snapshot(mock_asterisk_env)
    mocker.patch(f"{PROVISIONING}.read_mac_addr", return_value=NEW_MAC)
    mocker.patch(
        f"{PROVISIONING}.ConfigTransaction.__enter__",
        side_effect=FileTransactionError("Backup failed"),
    )
    with pytest.raises(AsteriskServiceError, match="Backup failed"):
        replace_phone("ext", "1001")
    _assert_untouched(mock_asterisk_env, before)


def test_replace_phone_old_xml_delete_fails(
    mock_asterisk_env: dict[str, Path],
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If the old XML can't be deleted, the replacement still completes."""
    mocker.patch(f"{PROVISIONING}.read_mac_addr", return_value=NEW_MAC)
    mocker.patch(
        f"{PROVISIONING}._remove_cnf_xml",
        side_effect=FileTransactionError("permission denied"),
    )

    replace_phone("ext", "1001")

    assert f"[SEP{NEW_MAC}]" in mock_asterisk_env["sip_conf"].read_text(
        encoding="utf-8"
    )
    assert _new_xml(mock_asterisk_env).exists()
    assert "Remove it manually" in caplog.text
    assert str(mock_asterisk_env["existing_xml"]) in caplog.text


def test_replace_phone_no_old_xml(
    mock_asterisk_env: dict[str, Path],
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A missing old XML is only a warning; the replacement completes."""
    mock_asterisk_env["existing_xml"].unlink()
    mocker.patch(f"{PROVISIONING}.read_mac_addr", return_value=NEW_MAC)

    replace_phone("ext", "1001")

    assert "No old .cnf.xml file found" in caplog.text
    assert _new_xml(mock_asterisk_env).exists()


@pytest.mark.usefixtures("mock_asterisk_env")
def test_replace_phone_invalid_method() -> None:
    """An unknown search method is rejected."""
    with pytest.raises(AsteriskCliError, match="No option selected"):
        replace_phone("invalid", "1001")


@pytest.mark.usefixtures("mock_asterisk_env")
@pytest.mark.parametrize(
    ("phone", "voicemail"),
    [
        (
            Phone(extension="12", mac_address="999999999999", caller_id="x"),
            None,
        ),
        (Phone(extension="9999", mac_address="ZZ", caller_id="x"), None),
        (
            Phone(
                extension="9999",
                mac_address="999999999999",
                caller_id='"x"\n[evil](phone)',
            ),
            None,
        ),
        (
            Phone(extension="9999", mac_address="999999999999", caller_id="x"),
            Voicemail(name="Jane, Admin", email="jane@example.com"),
        ),
        (
            Phone(extension="9999", mac_address="999999999999", caller_id="x"),
            Voicemail(name="Jane", email="jane|x@example.com"),
        ),
        (
            Phone(extension="9999", mac_address="999999999999", caller_id="x"),
            Voicemail(name="Jane", email="not-an-email"),
        ),
    ],
)
def test_register_phone_rejects_invalid_fields(
    phone: Phone, voicemail: Voicemail | None, mocker: MockerFixture
) -> None:
    """Invalid fields are rejected before anything is provisioned."""
    mock_provision = mocker.patch(
        "asterisk_phone_management.services.provisioning._provision_phone"
    )
    with pytest.raises(AsteriskCliError):
        register_phone(phone, voicemail)
    mock_provision.assert_not_called()
