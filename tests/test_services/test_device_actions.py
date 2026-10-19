"""Unit tests for device actions, SSH commands, and Asterisk interactions."""

import subprocess

import pexpect
import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    AsteriskServiceError,
    DeviceCommunicationError,
)
from asterisk_phone_management.services.device_actions import (
    _get_ip_address,
    _invoke_phone_reboot,
    _is_asterisk_running,
    _send_reboot_command,
    get_active_calls,
    reboot_phone,
    reload_asterisk,
    reload_asterisk_module,
)


def test_get_ip_address_success(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.stdout = "Addr->IP : 192.168.1.50:5060\n"

    ip = _get_ip_address("112233445566")
    assert ip == "192.168.1.50"


def test_get_ip_address_invalid_or_zero(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.stdout = "Addr->IP : 0.0.0.0:5060\n"

    with pytest.raises(
        DeviceCommunicationError, match="Could not resolve an IP address"
    ):
        _get_ip_address("112233445566")


def test_get_ip_address_subprocess_failure(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")

    with pytest.raises(
        DeviceCommunicationError, match="Failed to get IP address"
    ):
        _get_ip_address("112233445566")


def test_get_ip_address_no_regex_match(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("subprocess.run")

    mock_run.return_value.stdout = "Description: SIP Peer\nStatus: OK\n"

    with pytest.raises(
        DeviceCommunicationError, match="Could not resolve an IP address"
    ):
        _get_ip_address("112233445566")


def test_send_reboot_command(mocker: MockerFixture) -> None:
    mock_child = mocker.MagicMock()
    _send_reboot_command(mock_child, "password123")
    assert mock_child.sendline.call_count == 4


def test_invoke_phone_reboot_success(mocker: MockerFixture) -> None:
    mocker.patch("pexpect.spawn")
    mocker.patch(
        "asterisk_phone_management.services.device_actions._send_reboot_command"
    )

    assert _invoke_phone_reboot("192.168.1.50", "admin", "cisco") is True


def test_invoke_phone_reboot_success_else_block(mocker: MockerFixture) -> None:
    mocker.patch("pexpect.spawn")
    mocker.patch(
        "asterisk_phone_management.services.device_actions._send_reboot_command",
        return_value=None,
    )
    assert _invoke_phone_reboot("192.168.1.50", "admin", "cisco") is True


def test_invoke_phone_reboot_timeout_or_eof(mocker: MockerFixture) -> None:
    mocker.patch("pexpect.spawn", side_effect=pexpect.TIMEOUT("Timeout"))
    assert _invoke_phone_reboot("192.168.1.50", "admin", "cisco") is True


def test_invoke_phone_reboot_exception(mocker: MockerFixture) -> None:
    mocker.patch("pexpect.spawn", side_effect=OSError("Connection failed"))
    assert _invoke_phone_reboot("192.168.1.50", "admin", "cisco") is False


def test_is_asterisk_running_true(mocker: MockerFixture) -> None:
    mocker.patch("shutil.which", return_value="/usr/bin/pgrep")
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0

    assert _is_asterisk_running() is True


def test_is_asterisk_running_false(mocker: MockerFixture) -> None:
    mocker.patch("shutil.which", return_value="/usr/bin/pgrep")
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 1

    assert _is_asterisk_running() is False


def test_is_asterisk_running_missing_pgrep(mocker: MockerFixture) -> None:
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(
        AsteriskCliError, match="The 'pgrep' command was not found"
    ):
        _is_asterisk_running()


def test_is_asterisk_running_oserror(mocker: MockerFixture) -> None:
    mocker.patch("shutil.which", return_value="/usr/bin/pgrep")
    mocker.patch("subprocess.run", side_effect=OSError("Execution error"))

    with pytest.raises(AsteriskCliError, match="Failed to execute pgrep"):
        _is_asterisk_running()


def test_reload_asterisk_module_success(mocker: MockerFixture) -> None:
    mocker.patch("shutil.which", return_value="/usr/sbin/asterisk")
    mock_run = mocker.patch("subprocess.run")

    reload_asterisk_module("sip reload", "SIP configuration")
    mock_run.assert_called_once_with(
        ["/usr/sbin/asterisk", "-rx", "sip reload"],
        check=True,
        capture_output=True,
        text=True,
    )


def test_reload_asterisk_module_missing_binary(mocker: MockerFixture) -> None:
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(
        AsteriskCliError, match="The 'asterisk' command was not found"
    ):
        reload_asterisk_module("sip reload", "SIP configuration")


def test_reload_asterisk_module_failure(mocker: MockerFixture) -> None:
    mocker.patch("shutil.which", return_value="/usr/sbin/asterisk")
    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = subprocess.CalledProcessError(
        1, "cmd", stderr="Reload error"
    )

    with pytest.raises(
        AsteriskServiceError, match="Failed to reload SIP configuration"
    ):
        reload_asterisk_module("sip reload", "SIP configuration")


def test_reload_asterisk_full_flow(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.services.device_actions._is_asterisk_running",
        return_value=True,
    )
    mock_reload_mod = mocker.patch(
        "asterisk_phone_management.services.device_actions.reload_asterisk_module"
    )

    reload_asterisk()

    assert mock_reload_mod.call_count == 3


def test_reload_asterisk_not_running(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.services.device_actions._is_asterisk_running",
        return_value=False,
    )

    with pytest.raises(AsteriskServiceError, match="Asterisk is not running"):
        reload_asterisk()


def test_get_active_calls_parsing(mocker: MockerFixture) -> None:
    raw_output = (
        "SIP/SEP112233445566-00000001!default!1001!1!Up!Dial!SIP/SEP2!1002!Alice!!DOCUMENTATION!120!SIP/SEP2-00000002\n"
        "invalid!line\n"
    )
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.stdout = raw_output

    calls = get_active_calls()

    assert len(calls) == 1
    call = calls[0]
    assert call.channel == "SIP/SEP112233445566-00000001"
    assert call.extension == "1001"
    assert call.duration == "120"


def test_get_active_calls_called_process_error(mocker: MockerFixture) -> None:
    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "cmd"),
    )
    assert get_active_calls() == []


def test_get_active_calls_file_not_found(mocker: MockerFixture) -> None:
    mocker.patch(
        "subprocess.run",
        side_effect=FileNotFoundError("Not found"),
    )
    assert get_active_calls() == []


def test_get_active_calls_empty_line(mocker: MockerFixture) -> None:
    raw_output = (
        "SIP/SEP112233445566-00000001!default!1001!1!Up!Dial!SIP/SEP2!1002!Alice!!DOCUMENTATION!120!SIP/SEP2-00000002\n"
        "\n"  # Creates an explicitly empty string when split by \n
        "SIP/SEP223344556677-00000002!default!1002!1!Up!Dial!SIP/SEP1!1001!Bob!!DOCUMENTATION!120!\n"
    )
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.stdout = raw_output
    calls = get_active_calls()

    assert len(calls) == 2


def test_reboot_phone_flow(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.services.device_actions.search_for_extension",
        return_value=["match"],
    )
    mocker.patch(
        "asterisk_phone_management.services.device_actions.get_mac_from_ext",
        return_value="112233445566",
    )
    mocker.patch(
        "asterisk_phone_management.services.device_actions._get_ip_address",
        return_value="192.168.1.50",
    )
    mock_invoke = mocker.patch(
        "asterisk_phone_management.services.device_actions._invoke_phone_reboot",
        return_value=True,
    )

    reboot_phone("1001")

    mock_invoke.assert_called_once_with(
        ip_address="192.168.1.50",
        username="admin",
        password="cisco",
    )


def test_reboot_phone_failure(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.services.device_actions.search_for_extension",
        return_value=["match"],
    )
    mocker.patch(
        "asterisk_phone_management.services.device_actions.get_mac_from_ext",
        return_value="112233445566",
    )
    mocker.patch(
        "asterisk_phone_management.services.device_actions._get_ip_address",
        return_value="192.168.1.100",
    )
    mocker.patch(
        "asterisk_phone_management.services.device_actions._invoke_phone_reboot",
        return_value=False,
    )

    with pytest.raises(
        DeviceCommunicationError, match="Failed to deliver reboot command"
    ):
        reboot_phone("1001")


def test_reboot_phone_rejects_invalid_extension(mocker: MockerFixture) -> None:
    """A partial extension is rejected before any phone is looked up."""
    mock_search = mocker.patch(
        "asterisk_phone_management.services.device_actions.search_for_extension"
    )
    with pytest.raises(AsteriskCliError, match="4 digits"):
        reboot_phone("1")
    mock_search.assert_not_called()
