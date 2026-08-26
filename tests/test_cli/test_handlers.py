"""Unit tests for CLI user command handlers."""

from pytest_mock import MockerFixture

from src.cli.handlers import (
    handle_reboot_phone,
    handle_register_phone,
    handle_remove_phone,
    handle_replace_phone,
    handle_reset_vm_password,
    handle_search_for_extension,
    handle_search_for_mac_address,
)
from src.schemas.models import Phone, Voicemail


def test_handle_search_for_extension(mocker: MockerFixture) -> None:
    mocker.patch("src.cli.handlers.read_extension", return_value="1001")
    mock_search = mocker.patch("src.cli.handlers.search_for_extension")

    handle_search_for_extension()

    mock_search.assert_called_once_with("1001")


def test_handle_search_for_mac_address(mocker: MockerFixture) -> None:
    mocker.patch("src.cli.handlers.read_mac_addr", return_value="AABBCCDDEEFF")
    mock_search = mocker.patch("src.cli.handlers.search_for_mac_address")

    handle_search_for_mac_address()

    mock_search.assert_called_once_with("AABBCCDDEEFF")


def test_handle_register_phone_without_voicemail(
    mocker: MockerFixture,
) -> None:
    mocker.patch("src.cli.handlers.read_extension", return_value="1001")
    mocker.patch("src.cli.handlers.read_mac_addr", return_value="AABBCCDDEEFF")
    mocker.patch(
        "src.cli.handlers.read_caller_id", return_value='"John" <1001>'
    )
    mocker.patch("src.cli.handlers.prompt_use_voicemail", return_value=False)
    mock_register = mocker.patch("src.cli.handlers.register_phone")

    handle_register_phone()

    expected_phone = Phone(
        extension="1001", mac_address="AABBCCDDEEFF", caller_id='"John" <1001>'
    )
    mock_register.assert_called_once_with(expected_phone, None)


def test_handle_register_phone_with_voicemail(mocker: MockerFixture) -> None:
    mocker.patch("src.cli.handlers.read_extension", return_value="1001")
    mocker.patch("src.cli.handlers.read_mac_addr", return_value="AABBCCDDEEFF")
    mocker.patch(
        "src.cli.handlers.read_caller_id", return_value='"John" <1001>'
    )
    mocker.patch("src.cli.handlers.prompt_use_voicemail", return_value=True)

    mocker.patch("src.cli.handlers.read_name", return_value="John Doe")
    mocker.patch(
        "src.cli.handlers.read_email", return_value="john@example.com"
    )

    mock_register = mocker.patch("src.cli.handlers.register_phone")

    handle_register_phone()

    expected_phone = Phone(
        extension="1001", mac_address="AABBCCDDEEFF", caller_id='"John" <1001>'
    )
    expected_vm = Voicemail(name="John Doe", email="john@example.com")

    mock_register.assert_called_once_with(expected_phone, expected_vm)


def test_handle_remove_phone_by_ext(mocker: MockerFixture) -> None:
    mocker.patch("src.cli.handlers.prompt_search_method", return_value="ext")
    mocker.patch("src.cli.handlers.read_extension", return_value="1001")
    mock_remove = mocker.patch("src.cli.handlers.remove_phone")

    handle_remove_phone()

    mock_remove.assert_called_once_with("ext", "1001")


def test_handle_remove_phone_by_mac(mocker: MockerFixture) -> None:
    mocker.patch("src.cli.handlers.prompt_search_method", return_value="mac")
    mocker.patch("src.cli.handlers.read_mac_addr", return_value="AABBCCDDEEFF")

    mock_remove = mocker.patch("src.cli.handlers.remove_phone")

    handle_remove_phone()
    mock_remove.assert_called_once_with("mac", "AABBCCDDEEFF")


def test_handle_remove_phone_invalid_method(mocker: MockerFixture) -> None:
    mocker.patch(
        "src.cli.handlers.prompt_search_method", return_value="invalid"
    )
    mock_remove = mocker.patch("src.cli.handlers.remove_phone")

    handle_remove_phone()
    mock_remove.assert_not_called()


def test_handle_replace_phone_by_ext(mocker: MockerFixture) -> None:
    mocker.patch("src.cli.handlers.prompt_search_method", return_value="ext")
    mocker.patch("src.cli.handlers.read_extension", return_value="1001")
    mock_replace = mocker.patch("src.cli.handlers.replace_phone")

    handle_replace_phone()

    mock_replace.assert_called_once_with("ext", "1001")


def test_handle_replace_phone_by_mac(mocker: MockerFixture) -> None:
    mocker.patch("src.cli.handlers.prompt_search_method", return_value="mac")
    mocker.patch("src.cli.handlers.read_mac_addr", return_value="AABBCCDDEEFF")
    mock_replace = mocker.patch("src.cli.handlers.replace_phone")

    handle_replace_phone()

    mock_replace.assert_called_once_with("mac", "AABBCCDDEEFF")


def test_handle_replace_phone_invalid_method(mocker: MockerFixture) -> None:
    mocker.patch(
        "src.cli.handlers.prompt_search_method", return_value="invalid"
    )

    mock_replace = mocker.patch("src.cli.handlers.replace_phone")

    handle_replace_phone()

    mock_replace.assert_not_called()


def test_handle_reset_vm_password(mocker: MockerFixture) -> None:
    mocker.patch("src.cli.handlers.read_extension", return_value="1001")
    mocker.patch("src.cli.handlers.read_new_password", return_value="5678")
    mock_reset = mocker.patch("src.cli.handlers.reset_vm_password")

    handle_reset_vm_password()

    mock_reset.assert_called_once_with("1001", "5678")


def test_handle_reboot_phone(mocker: MockerFixture) -> None:
    mocker.patch("src.cli.handlers.read_extension", return_value="1001")
    mock_reboot = mocker.patch("src.cli.handlers.reboot_phone")

    handle_reboot_phone()

    mock_reboot.assert_called_once_with("1001")
