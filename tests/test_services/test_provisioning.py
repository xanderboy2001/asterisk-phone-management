"""Unit tests for phone provisioning, deprovisioning, and replacement."""

import logging
import re
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    AsteriskServiceError,
    FileTransactionError,
)
from asterisk_phone_management.schemas.models import Phone, Voicemail
from asterisk_phone_management.services import provisioning
from asterisk_phone_management.services.provisioning import (
    _cleanup_created_files,
    _deprovision_phone,
    _patch_file,
    _provision_phone,
    _remove_cnf_xml,
    _replace_mac_in_file,
    _set_sip_secret,
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
def test_register_phone_normalizes_mac(mocker: MockerFixture) -> None:
    """A lowercase, colon-separated MAC is provisioned in normalized form."""
    mocker.patch("questionary.confirm").return_value.ask.return_value = True
    mock_provision = mocker.patch(
        "asterisk_phone_management.services.provisioning._provision_phone"
    )
    register_phone(
        Phone(extension="9999", mac_address="aa:bb:cc:dd:ee:ff", caller_id="")
    )
    mock_provision.assert_called_once_with(
        Phone(extension="9999", mac_address="AABBCCDDEEFF", caller_id=""),
        None,
    )


@pytest.mark.usefixtures("mock_asterisk_env")
def test_remove_phone_by_separated_mac(mocker: MockerFixture) -> None:
    """Removing by a separated, lowercase MAC finds the phone."""
    mocker.patch("questionary.confirm").return_value.ask.return_value = True
    mock_deprov = mocker.patch(
        "asterisk_phone_management.services.provisioning._deprovision_phone"
    )
    remove_phone("mac", "11:22:33:44:55:66")
    mock_deprov.assert_called_once_with("1001", "112233445566")


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


def test_deprovision_phone_keeps_longer_extensions(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """Removing 1001 never deletes lines that belong to 10012 (F-13)."""
    ext_conf = mock_asterisk_env["ext_conf"]
    vm_conf = mock_asterisk_env["vm_conf"]
    ext_conf.write_text(
        ext_conf.read_text(encoding="utf-8")
        + "exten=>1001,2,Hangup()\n"
        + "exten => 10012,1,Dial(SIP/SEPAABBCCDDEEFF,14,t)\n",
        encoding="utf-8",
    )
    vm_conf.write_text(
        vm_conf.read_text(encoding="utf-8") + "10012 = 9999, Jane, j@x.com\n",
        encoding="utf-8",
    )

    _deprovision_phone("1001", "112233445566")

    ext_text = ext_conf.read_text(encoding="utf-8")
    vm_text = vm_conf.read_text(encoding="utf-8")
    assert "exten => 10012,1" in ext_text
    assert "exten=>1001," not in ext_text
    assert "exten => 1001," not in ext_text
    assert "10012 = 9999" in vm_text
    assert "1001 = 1234" not in vm_text


# --- F-15: every config write is atomic ---


def test_patch_file_appends_and_keeps_permissions(tmp_path: Path) -> None:
    """Appending rewrites the file atomically and keeps its mode."""
    conf = tmp_path / "sip.conf"
    conf.write_text("a\n", encoding="utf-8")
    conf.chmod(0o640)

    _patch_file(conf, "b\n")

    assert conf.read_text(encoding="utf-8") == "a\nb\n"
    assert conf.stat().st_mode & 0o777 == 0o640
    assert list(tmp_path.glob(".*.tmp")) == []


def test_provision_phone_keeps_config_permissions(
    mock_asterisk_env: dict[str, Path],
    sample_phone: Phone,
    sample_voicemail: Voicemail,
) -> None:
    """Registering a phone doesn't change the config files' modes."""
    confs = [mock_asterisk_env[k] for k in ("sip_conf", "ext_conf", "vm_conf")]
    for conf in confs:
        conf.chmod(0o640)

    _provision_phone(sample_phone, sample_voicemail)

    assert [c.stat().st_mode & 0o777 for c in confs] == [0o640] * 3


def test_provisioning_never_writes_in_place(
    mock_asterisk_env: dict[str, Path],
    sample_phone: Phone,
    sample_voicemail: Voicemail,
    mocker: MockerFixture,
) -> None:
    """Register, replace, and remove only write through atomic_write_text."""
    del mock_asterisk_env
    mocker.patch.object(
        Path,
        "write_text",
        side_effect=AssertionError("use atomic_write_text"),
    )

    _provision_phone(sample_phone, sample_voicemail)
    _deprovision_phone(sample_phone.extension, sample_phone.mac_address)


# --- F-04: SIP secrets are random, never SEP<MAC> ---


def _secret_for(sip_text: str, mac: str) -> str:
    """Return the secret= value from one phone's sip.conf section.

    Args:
        sip_text: The contents of sip.conf.
        mac: The phone's MAC address.

    Returns:
        The secret in that phone's section.
    """
    section = sip_text.split(f"[SEP{mac}]", 1)[1].split("\n[", 1)[0]
    match = re.search(r"^secret=(.*)$", section, flags=re.MULTILINE)
    assert match is not None
    return str(match.group(1))


def _xml_secret(xml_path: Path) -> str:
    """Return the <authPassword> value from a phone's .cnf.xml.

    Args:
        xml_path: The phone's .cnf.xml file.

    Returns:
        The password in the file.
    """
    match = re.search(
        r"<authPassword>(.*?)</authPassword>",
        xml_path.read_text(encoding="utf-8"),
    )
    assert match is not None
    return str(match.group(1))


def test_provision_phone_uses_random_secret(
    mock_asterisk_env: dict[str, Path], sample_phone: Phone
) -> None:
    """sip.conf and the .cnf.xml get the same random, non-MAC secret."""
    _provision_phone(sample_phone, None)

    sip = mock_asterisk_env["sip_conf"].read_text(encoding="utf-8")
    secret = _secret_for(sip, sample_phone.mac_address)
    xml = (
        mock_asterisk_env["tftp_dir"]
        / f"SEP{sample_phone.mac_address}.cnf.xml"
    )

    assert sample_phone.mac_address not in secret
    assert re.fullmatch(r"[A-Za-z0-9_-]{24}", secret)
    assert _xml_secret(xml) == secret
    assert f"authname=SEP{sample_phone.mac_address}" in sip


def test_provisioned_phones_get_different_secrets(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """Two phones never share a secret."""
    first = Phone(extension="2001", mac_address="AAAAAAAAAAAA", caller_id="")
    second = Phone(extension="2002", mac_address="BBBBBBBBBBBB", caller_id="")

    _provision_phone(first, None)
    _provision_phone(second, None)

    sip = mock_asterisk_env["sip_conf"].read_text(encoding="utf-8")
    assert _secret_for(sip, first.mac_address) != _secret_for(
        sip, second.mac_address
    )


def test_provision_phone_does_not_log_secret_value(
    mock_asterisk_env: dict[str, Path],
    sample_phone: Phone,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The generated secret never appears in the log."""
    with caplog.at_level(logging.DEBUG):
        _provision_phone(sample_phone, None)

    sip = mock_asterisk_env["sip_conf"].read_text(encoding="utf-8")
    assert _secret_for(sip, sample_phone.mac_address) not in caplog.text


@pytest.mark.parametrize("template", ["missing", "no-placeholder"])
def test_provision_phone_needs_secret_placeholder(
    mock_asterisk_env: dict[str, Path], sample_phone: Phone, template: str
) -> None:
    """Without --SIPSECRET-- in the template, nothing is provisioned."""
    xml_template = mock_asterisk_env["xml_template"]
    if template == "missing":
        xml_template.unlink()
    else:
        xml_template.write_text(
            "<device><name>--SEPMAC--</name></device>\n", encoding="utf-8"
        )
    before = _snapshot(mock_asterisk_env)

    with pytest.raises(AsteriskServiceError, match=r"template|--SIPSECRET--"):
        _provision_phone(sample_phone, None)

    assert _snapshot(mock_asterisk_env) == before
    new_xml = (
        mock_asterisk_env["tftp_dir"]
        / f"SEP{sample_phone.mac_address}.cnf.xml"
    )
    assert not new_xml.exists()


def test_replace_phone_issues_new_secret(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """A replaced phone drops its SEP<MAC> secret for a random one."""
    mocker.patch(f"{PROVISIONING}.read_mac_addr", return_value=NEW_MAC)

    replace_phone("ext", "1001")

    sip = mock_asterisk_env["sip_conf"].read_text(encoding="utf-8")
    secret = _secret_for(sip, NEW_MAC)
    assert not secret.startswith("SEP")
    assert _xml_secret(_new_xml(mock_asterisk_env)) == secret


def test_replace_phone_without_secret_line_rolls_back(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """If the section has no secret= line, nothing changes."""
    sip_conf = mock_asterisk_env["sip_conf"]
    sip_conf.write_text(
        "\n".join(
            line
            for line in sip_conf.read_text(encoding="utf-8").splitlines()
            if not line.startswith("secret=")
        )
        + "\n",
        encoding="utf-8",
    )
    before = _snapshot(mock_asterisk_env)
    mocker.patch(f"{PROVISIONING}.read_mac_addr", return_value=NEW_MAC)

    with pytest.raises(AsteriskServiceError, match="found 0"):
        replace_phone("ext", "1001")

    _assert_untouched(mock_asterisk_env, before)


def test_replace_phone_needs_secret_placeholder(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """An old template without --SIPSECRET-- leaves the old phone alone."""
    mock_asterisk_env["xml_template"].write_text(
        "<device><name>--SEPMAC--</name></device>\n", encoding="utf-8"
    )
    before = _snapshot(mock_asterisk_env)
    mocker.patch(f"{PROVISIONING}.read_mac_addr", return_value=NEW_MAC)

    with pytest.raises(AsteriskServiceError, match="--SIPSECRET--"):
        replace_phone("ext", "1001")

    _assert_untouched(mock_asterisk_env, before)


def test_set_sip_secret_changes_only_target_section(tmp_path: Path) -> None:
    """Other phones, indentation, and trailing comments are kept."""
    sip_conf = tmp_path / "sip.conf"
    sip_conf.write_text(
        "[general]\n"
        "secret=general\n"
        "[SEP112233445566](phone)\n"
        "  secret = old ; keep me\n"
        "callerid=x\n"
        "[SEPAABBCCDDEEFF](phone)\n"
        "secret=other\n",
        encoding="utf-8",
    )

    _set_sip_secret(sip_conf, "112233445566", "NEW")

    assert sip_conf.read_text(encoding="utf-8") == (
        "[general]\n"
        "secret=general\n"
        "[SEP112233445566](phone)\n"
        "  secret = NEW; keep me\n"
        "callerid=x\n"
        "[SEPAABBCCDDEEFF](phone)\n"
        "secret=other\n"
    )


def test_set_sip_secret_matches_lowercase_section(tmp_path: Path) -> None:
    """A section header written in lowercase is still found."""
    sip_conf = tmp_path / "sip.conf"
    sip_conf.write_text("[sep112233445566](phone)\nSECRET=>old\n", "utf-8")

    _set_sip_secret(sip_conf, "112233445566", "NEW")

    assert sip_conf.read_text(encoding="utf-8").endswith("SECRET=>NEW\n")


def test_set_sip_secret_refuses_two_secret_lines(tmp_path: Path) -> None:
    """Two secret= lines in one section is ambiguous, so nothing changes."""
    sip_conf = tmp_path / "sip.conf"
    original = "[SEP112233445566](phone)\nsecret=a\nsecret=b\n"
    sip_conf.write_text(original, encoding="utf-8")

    with pytest.raises(AsteriskCliError, match="found 2"):
        _set_sip_secret(sip_conf, "112233445566", "NEW")

    assert sip_conf.read_text(encoding="utf-8") == original


LEGACY_TEMPLATE = (
    "<device><name>--SEPMAC--</name>"
    "<featureLabel>--EXTENNUMBER--</featureLabel>"
    "<authPassword>--SEPMAC--</authPassword></device>\n"
)


@pytest.fixture
def legacy_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn on the legacy SEP<MAC> secret mode."""
    monkeypatch.setattr(provisioning, "SIP_SECRET_MODE", "mac")


@pytest.mark.usefixtures("legacy_secrets")
def test_legacy_mode_uses_mac_secret(
    mock_asterisk_env: dict[str, Path],
    sample_phone: Phone,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Legacy mode writes SEP<MAC> and works with the old template."""
    mock_asterisk_env["xml_template"].write_text(LEGACY_TEMPLATE, "utf-8")
    mac = sample_phone.mac_address

    _provision_phone(sample_phone, None)

    sip = mock_asterisk_env["sip_conf"].read_text("utf-8")
    xml = mock_asterisk_env["tftp_dir"] / f"SEP{mac}.cnf.xml"
    assert _secret_for(sip, mac) == f"SEP{mac}"
    assert _xml_secret(xml) == f"SEP{mac}"
    assert "Legacy SIP secret mode is on" in caplog.text


@pytest.mark.usefixtures("legacy_secrets")
def test_legacy_mode_fills_new_placeholder(
    mock_asterisk_env: dict[str, Path], sample_phone: Phone
) -> None:
    """With the new template, legacy mode puts SEP<MAC> in --SIPSECRET--."""
    mac = sample_phone.mac_address

    _provision_phone(sample_phone, None)

    xml = mock_asterisk_env["tftp_dir"] / f"SEP{mac}.cnf.xml"
    assert _xml_secret(xml) == f"SEP{mac}"


@pytest.mark.usefixtures("legacy_secrets")
def test_legacy_mode_replace_keeps_old_behaviour(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """Replacing in legacy mode gives SEP<new MAC>, as before F-04."""
    mock_asterisk_env["xml_template"].write_text(LEGACY_TEMPLATE, "utf-8")
    mocker.patch(f"{PROVISIONING}.read_mac_addr", return_value=NEW_MAC)

    replace_phone("ext", "1001")

    sip = mock_asterisk_env["sip_conf"].read_text(encoding="utf-8")
    assert _secret_for(sip, NEW_MAC) == f"SEP{NEW_MAC}"
    assert _xml_secret(_new_xml(mock_asterisk_env)) == f"SEP{NEW_MAC}"


@pytest.mark.parametrize("mode", ["MAC", " mac ", "Random"])
def test_secret_mode_ignores_case_and_spaces(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """The setting is trimmed and case-insensitive."""
    monkeypatch.setattr(provisioning, "SIP_SECRET_MODE", mode)
    assert provisioning._secret_mode() == mode.strip().lower()


def test_invalid_secret_mode_changes_nothing(
    mock_asterisk_env: dict[str, Path],
    sample_phone: Phone,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typo in the setting stops register and replace before any write."""
    monkeypatch.setattr(provisioning, "SIP_SECRET_MODE", "macc")
    before = _snapshot(mock_asterisk_env)

    with pytest.raises(AsteriskServiceError, match="'random' or 'mac'"):
        _provision_phone(sample_phone, None)
    assert _snapshot(mock_asterisk_env) == before

    mocker.patch(f"{PROVISIONING}.read_mac_addr", return_value=NEW_MAC)
    with pytest.raises(AsteriskCliError, match="'random' or 'mac'"):
        replace_phone("ext", "1001")
    _assert_untouched(mock_asterisk_env, before)
