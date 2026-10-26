"""Unit tests for device actions, SSH commands, and Asterisk interactions."""

import subprocess
from unittest.mock import MagicMock, call

import pexpect
import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    AsteriskServiceError,
    DeviceCommunicationError,
)
from asterisk_phone_management.services import device_actions
from asterisk_phone_management.services.device_actions import reboot_phone


@pytest.fixture
def phone_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide fake phone SSH credentials for reboot tests."""
    monkeypatch.setattr(device_actions, "PHONE_SSH_USER", "test-user")
    monkeypatch.setattr(device_actions, "PHONE_SSH_PASS", "test-pass")


def test_get_ip_address_success(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.stdout = "Addr->IP : 192.168.1.50:5060\n"

    ip = device_actions._get_ip_address("112233445566")
    assert ip == "192.168.1.50"


def test_get_ip_address_invalid_or_zero(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.stdout = "Addr->IP : 0.0.0.0:5060\n"

    with pytest.raises(
        DeviceCommunicationError, match="Could not resolve an IP address"
    ):
        device_actions._get_ip_address("112233445566")


def test_get_ip_address_subprocess_failure(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")

    with pytest.raises(
        DeviceCommunicationError, match="Failed to get IP address"
    ):
        device_actions._get_ip_address("112233445566")


def test_get_ip_address_no_regex_match(mocker: MockerFixture) -> None:
    mock_run = mocker.patch("subprocess.run")

    mock_run.return_value.stdout = "Description: SIP Peer\nStatus: OK\n"

    with pytest.raises(
        DeviceCommunicationError, match="Could not resolve an IP address"
    ):
        device_actions._get_ip_address("112233445566")


PROMPTS = ("password:", "login:", "Password:", "DEBUG>")


def _child(expect_results: list[object]) -> MagicMock:
    """Build a fake ssh session whose ``expect`` calls return in order.

    Args:
        expect_results: Return values (or exceptions to raise) for each
            successive ``expect`` call.

    Returns:
        The fake spawned process.
    """
    child = MagicMock()
    child.expect.side_effect = expect_results
    return child


def test_send_reboot_command_follows_dialogue() -> None:
    """Every prompt is answered in order, then the session end is awaited."""
    child = _child([0, 0, 0, 0, 0])
    device_actions._send_reboot_command(child, "test-pass")
    assert child.expect.call_args_list == [
        *(call(prompt) for prompt in PROMPTS),
        call([pexpect.EOF, pexpect.TIMEOUT]),
    ]
    assert child.sendline.call_args_list == [
        call("test-pass"),
        call("debug"),
        call("debug"),
        call("reboot"),
    ]


@pytest.mark.parametrize("error", [pexpect.TIMEOUT, pexpect.EOF])
@pytest.mark.parametrize("failing_step", range(len(PROMPTS)))
def test_send_reboot_command_stops_before_reboot(
    failing_step: int, error: type[Exception]
) -> None:
    """A missing prompt raises and ``reboot`` is never sent."""
    child = _child([0] * failing_step + [error("no prompt")])
    with pytest.raises(error):
        device_actions._send_reboot_command(child, "test-pass")
    assert call("reboot") not in child.sendline.call_args_list


def test_ssh_args_put_options_before_destination() -> None:
    """Options precede ``--`` and the destination is always last."""
    args = device_actions._ssh_args("test-user", "192.168.1.50", 5)
    assert args[-2:] == ["--", "test-user@192.168.1.50"]
    assert "StrictHostKeyChecking=accept-new" in args
    assert "ConnectTimeout=5" in args
    assert "NumberOfPasswordPrompts=1" in args


@pytest.mark.parametrize("final_match", [0, 1], ids=["eof", "timeout"])
def test_invoke_phone_reboot_success(
    mocker: MockerFixture, final_match: int
) -> None:
    """Hanging up or going quiet after ``reboot`` both count as success."""
    child = _child([0, 0, 0, 0, final_match])
    spawn = mocker.patch.object(
        device_actions.pexpect, "spawn", return_value=child
    )
    assert device_actions._invoke_phone_reboot(
        "192.168.1.50", "test-user", "test-pass", timeout=7
    )
    spawn.assert_called_once_with(
        command="ssh",
        args=device_actions._ssh_args("test-user", "192.168.1.50", 7),
        encoding="utf-8",
        timeout=7,
    )
    child.close.assert_called_once_with(force=True)


@pytest.mark.parametrize("error", [pexpect.TIMEOUT, pexpect.EOF])
@pytest.mark.parametrize("failing_step", range(len(PROMPTS)))
def test_invoke_phone_reboot_fails_before_reboot(
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
    failing_step: int,
    error: type[Exception],
) -> None:
    """Unreachable, wrong password, or unexpected prompt returns False."""
    child = _child([0] * failing_step + [error("no prompt")])
    mocker.patch.object(device_actions.pexpect, "spawn", return_value=child)
    assert not device_actions._invoke_phone_reboot(
        "192.168.1.50", "test-user", "test-pass"
    )
    assert "192.168.1.50" in caplog.text
    assert "test-pass" not in caplog.text
    child.close.assert_called_once_with(force=True)


@pytest.mark.parametrize(
    "error",
    [OSError("ssh not found"), pexpect.ExceptionPexpect("spawn failed")],
)
def test_invoke_phone_reboot_spawn_failure(
    mocker: MockerFixture, error: Exception
) -> None:
    """If ssh can't start there is nothing to close and False is returned."""
    mocker.patch.object(device_actions.pexpect, "spawn", side_effect=error)
    assert not device_actions._invoke_phone_reboot(
        "192.168.1.50", "test-user", "test-pass"
    )


def test_invoke_phone_reboot_session_error(mocker: MockerFixture) -> None:
    """Other pexpect errors mid-session return False and still close ssh."""
    child = _child([pexpect.ExceptionPexpect("read failed")])
    mocker.patch.object(device_actions.pexpect, "spawn", return_value=child)
    assert not device_actions._invoke_phone_reboot(
        "192.168.1.50", "test-user", "test-pass"
    )
    child.close.assert_called_once_with(force=True)


def test_invoke_phone_reboot_ignores_close_errors(
    mocker: MockerFixture,
) -> None:
    """A failure while closing ssh doesn't hide a successful reboot."""
    child = _child([0, 0, 0, 0, 0])
    child.close.side_effect = pexpect.ExceptionPexpect("could not terminate")
    mocker.patch.object(device_actions.pexpect, "spawn", return_value=child)
    assert device_actions._invoke_phone_reboot(
        "192.168.1.50", "test-user", "test-pass"
    )


@pytest.mark.parametrize(
    ("user", "password", "missing"),
    [
        ("", "test-pass", "ASTERISK_CLI_PHONE_SSH_USER"),
        ("test-user", "", "ASTERISK_CLI_PHONE_SSH_PASS"),
        ("  ", "test-pass", "ASTERISK_CLI_PHONE_SSH_USER"),
        ("test-user", "  ", "ASTERISK_CLI_PHONE_SSH_PASS"),
        (
            "  ",
            "  ",
            "ASTERISK_CLI_PHONE_SSH_USER and ASTERISK_CLI_PHONE_SSH_PASS",
        ),
    ],
)
def test_reboot_phone_requires_credentials(
    monkeypatch: pytest.MonkeyPatch,
    mocker: MockerFixture,
    user: str,
    password: str,
    missing: str,
) -> None:
    """Missing or empty credentials fail before any phone is contacted."""
    monkeypatch.setattr(device_actions, "PHONE_SSH_USER", user)
    monkeypatch.setattr(device_actions, "PHONE_SSH_PASS", password)
    mocker.patch(
        "asterisk_phone_management.services.device_actions.search_for_extension"
    )
    mock_invoke = mocker.patch(
        "asterisk_phone_management.services.device_actions._invoke_phone_reboot"
    )
    with pytest.raises(AsteriskCliError, match=missing):
        reboot_phone("1001")
    mock_invoke.assert_not_called()


def test_is_asterisk_running_true(mocker: MockerFixture) -> None:
    mocker.patch("shutil.which", return_value="/usr/bin/pgrep")
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0

    assert device_actions._is_asterisk_running() is True


def test_is_asterisk_running_false(mocker: MockerFixture) -> None:
    mocker.patch("shutil.which", return_value="/usr/bin/pgrep")
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 1

    assert device_actions._is_asterisk_running() is False


def test_is_asterisk_running_missing_pgrep(mocker: MockerFixture) -> None:
    mocker.patch("shutil.which", return_value=None)

    with pytest.raises(
        AsteriskCliError, match="The 'pgrep' command was not found"
    ):
        device_actions._is_asterisk_running()


def test_is_asterisk_running_oserror(mocker: MockerFixture) -> None:
    mocker.patch("shutil.which", return_value="/usr/bin/pgrep")
    mocker.patch("subprocess.run", side_effect=OSError("Execution error"))

    with pytest.raises(AsteriskCliError, match="Failed to execute pgrep"):
        device_actions._is_asterisk_running()


def test_reload_asterisk_module_success(mocker: MockerFixture) -> None:
    mocker.patch("shutil.which", return_value="/usr/sbin/asterisk")
    mock_run = mocker.patch("subprocess.run")

    device_actions.reload_asterisk_module("sip reload", "SIP configuration")
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
        device_actions.reload_asterisk_module(
            "sip reload", "SIP configuration"
        )


def test_reload_asterisk_module_failure(mocker: MockerFixture) -> None:
    mocker.patch("shutil.which", return_value="/usr/sbin/asterisk")
    mock_run = mocker.patch("subprocess.run")
    mock_run.side_effect = subprocess.CalledProcessError(
        1, "cmd", stderr="Reload error"
    )

    with pytest.raises(
        AsteriskServiceError, match="Failed to reload SIP configuration"
    ):
        device_actions.reload_asterisk_module(
            "sip reload", "SIP configuration"
        )


def test_reload_asterisk_full_flow(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.services.device_actions._is_asterisk_running",
        return_value=True,
    )
    mock_reload_mod = mocker.patch(
        "asterisk_phone_management.services.device_actions.reload_asterisk_module"
    )

    device_actions.reload_asterisk()

    assert mock_reload_mod.call_count == 3


def test_reload_asterisk_not_running(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.services.device_actions._is_asterisk_running",
        return_value=False,
    )

    with pytest.raises(AsteriskServiceError, match="Asterisk is not running"):
        device_actions.reload_asterisk()


def test_get_active_calls_parsing(mocker: MockerFixture) -> None:
    raw_output = (
        "SIP/SEP112233445566-00000001!default!1001!1!Up!Dial!SIP/SEP2!1002!Alice!!DOCUMENTATION!120!SIP/SEP2-00000002\n"
        "invalid!line\n"
    )
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.stdout = raw_output

    calls = device_actions.get_active_calls()

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
    assert device_actions.get_active_calls() == []


def test_get_active_calls_file_not_found(mocker: MockerFixture) -> None:
    mocker.patch(
        "subprocess.run",
        side_effect=FileNotFoundError("Not found"),
    )
    assert device_actions.get_active_calls() == []


def test_get_active_calls_empty_line(mocker: MockerFixture) -> None:
    raw_output = (
        "SIP/SEP112233445566-00000001!default!1001!1!Up!Dial!SIP/SEP2!1002!Alice!!DOCUMENTATION!120!SIP/SEP2-00000002\n"
        "\n"  # Creates an explicitly empty string when split by \n
        "SIP/SEP223344556677-00000002!default!1002!1!Up!Dial!SIP/SEP1!1001!Bob!!DOCUMENTATION!120!\n"
    )
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.stdout = raw_output
    calls = device_actions.get_active_calls()

    assert len(calls) == 2


@pytest.mark.usefixtures("phone_credentials")
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

    device_actions.reboot_phone("1001")

    mock_invoke.assert_called_once_with(
        ip_address="192.168.1.50",
        username="test-user",
        password="test-pass",
    )


@pytest.mark.usefixtures("phone_credentials")
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
        device_actions.reboot_phone("1001")


def test_reboot_phone_rejects_invalid_extension(mocker: MockerFixture) -> None:
    """A partial extension is rejected before any phone is looked up."""
    mock_search = mocker.patch(
        "asterisk_phone_management.services.device_actions.search_for_extension"
    )
    with pytest.raises(AsteriskCliError, match="4 digits"):
        device_actions.reboot_phone("1")
    mock_search.assert_not_called()
