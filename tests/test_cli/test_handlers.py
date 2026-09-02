"""Unit tests for CLI user command handlers."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management.cli.handlers import (
    handle_edit_caller_id,
    handle_reboot_phone,
    handle_register_phone,
    handle_remove_phone,
    handle_replace_phone,
    handle_reset_vm_password,
    handle_search_for_caller_id,
    handle_search_for_extension,
    handle_search_for_mac_address,
)
from asterisk_phone_management.core.exceptions import AsteriskCliError
from asterisk_phone_management.schemas.models import (
    ConfigMatch,
    Phone,
    Voicemail,
)


def test_handle_search_for_extension(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_extension",
        return_value="1001",
    )
    mock_search = mocker.patch(
        "asterisk_phone_management.cli.handlers.search_for_extension"
    )

    handle_search_for_extension()

    mock_search.assert_called_once_with("1001")


def test_handle_search_for_mac_address(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_mac_addr",
        return_value="AABBCCDDEEFF",
    )
    mock_search = mocker.patch(
        "asterisk_phone_management.cli.handlers.search_for_mac_address"
    )

    handle_search_for_mac_address()

    mock_search.assert_called_once_with("AABBCCDDEEFF")


def test_handle_search_for_caller_id(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_search_query",
        return_value="John",
    )
    mock_search = mocker.patch(
        "asterisk_phone_management.cli.handlers.search_for_caller_id"
    )

    handle_search_for_caller_id()

    mock_search.assert_called_once_with("John")


def test_handle_register_phone_without_voicemail(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_extension",
        return_value="1001",
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_mac_addr",
        return_value="AABBCCDDEEFF",
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_caller_id",
        return_value='"John" <1001>',
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.prompt_use_voicemail",
        return_value=False,
    )
    mock_register = mocker.patch(
        "asterisk_phone_management.cli.handlers.register_phone"
    )

    handle_register_phone()

    expected_phone = Phone(
        extension="1001", mac_address="AABBCCDDEEFF", caller_id='"John" <1001>'
    )
    mock_register.assert_called_once_with(expected_phone, None)


def test_handle_register_phone_with_voicemail(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_extension",
        return_value="1001",
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_mac_addr",
        return_value="AABBCCDDEEFF",
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_caller_id",
        return_value='"John" <1001>',
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.prompt_use_voicemail",
        return_value=True,
    )

    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_name",
        return_value="John Doe",
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_email",
        return_value="john@example.com",
    )

    mock_register = mocker.patch(
        "asterisk_phone_management.cli.handlers.register_phone"
    )

    handle_register_phone()

    expected_phone = Phone(
        extension="1001", mac_address="AABBCCDDEEFF", caller_id='"John" <1001>'
    )
    expected_vm = Voicemail(name="John Doe", email="john@example.com")

    mock_register.assert_called_once_with(expected_phone, expected_vm)


def test_handle_remove_phone_by_ext(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.cli.handlers.prompt_search_method",
        return_value="ext",
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_extension",
        return_value="1001",
    )
    mock_remove = mocker.patch(
        "asterisk_phone_management.cli.handlers.remove_phone"
    )

    handle_remove_phone()

    mock_remove.assert_called_once_with("ext", "1001")


def test_handle_remove_phone_by_mac(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.cli.handlers.prompt_search_method",
        return_value="mac",
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_mac_addr",
        return_value="AABBCCDDEEFF",
    )

    mock_remove = mocker.patch(
        "asterisk_phone_management.cli.handlers.remove_phone"
    )

    handle_remove_phone()
    mock_remove.assert_called_once_with("mac", "AABBCCDDEEFF")


def test_handle_remove_phone_invalid_method(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.cli.handlers.prompt_search_method",
        return_value="invalid",
    )
    mock_remove = mocker.patch(
        "asterisk_phone_management.cli.handlers.remove_phone"
    )

    handle_remove_phone()
    mock_remove.assert_not_called()


def test_handle_replace_phone_by_ext(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.cli.handlers.prompt_search_method",
        return_value="ext",
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_extension",
        return_value="1001",
    )
    mock_replace = mocker.patch(
        "asterisk_phone_management.cli.handlers.replace_phone"
    )

    handle_replace_phone()

    mock_replace.assert_called_once_with("ext", "1001")


def test_handle_replace_phone_by_mac(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.cli.handlers.prompt_search_method",
        return_value="mac",
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_mac_addr",
        return_value="AABBCCDDEEFF",
    )
    mock_replace = mocker.patch(
        "asterisk_phone_management.cli.handlers.replace_phone"
    )

    handle_replace_phone()

    mock_replace.assert_called_once_with("mac", "AABBCCDDEEFF")


def test_handle_replace_phone_invalid_method(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.cli.handlers.prompt_search_method",
        return_value="invalid",
    )

    mock_replace = mocker.patch(
        "asterisk_phone_management.cli.handlers.replace_phone"
    )

    handle_replace_phone()

    mock_replace.assert_not_called()


def test_handle_reset_vm_password(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_extension",
        return_value="1001",
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_new_password",
        return_value="5678",
    )
    mock_reset = mocker.patch(
        "asterisk_phone_management.cli.handlers.reset_vm_password"
    )

    handle_reset_vm_password()

    mock_reset.assert_called_once_with("1001", "5678")


def test_handle_reboot_phone(mocker: MockerFixture) -> None:
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_extension",
        return_value="1001",
    )
    mock_reboot = mocker.patch(
        "asterisk_phone_management.cli.handlers.reboot_phone"
    )

    handle_reboot_phone()

    mock_reboot.assert_called_once_with("1001")


def test_handle_edit_caller_id_single_match(mocker: MockerFixture) -> None:
    """Test handle_edit_caller_id with a single caller ID match."""
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_extension",
        return_value="1001",
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_caller_id",
        return_value='"New Name" <1001>',
    )
    mock_search = mocker.patch(
        "asterisk_phone_management.cli.handlers.search_for_extension",
        return_value=[
            ConfigMatch(
                file_path=Path("sip.conf"),
                line_number=5,
                matched_text='callerid="Old Name" <1001>',
            )
        ],
    )
    mock_edit = mocker.patch(
        "asterisk_phone_management.cli.handlers.edit_caller_id"
    )

    handle_edit_caller_id()

    mock_edit.assert_called_once_with(
        mock_search.return_value, '"New Name" <1001>'
    )


def test_handle_edit_caller_id_no_extension_matches(
    mocker: MockerFixture,
) -> None:
    """Test handle_edit_caller_id raises when no extension matches found."""
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_extension",
        return_value="9999",
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_caller_id",
        return_value='"New Name" <9999>',
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.search_for_extension",
        return_value=[],
    )

    with pytest.raises(AsteriskCliError, match="No matches found for 9999"):
        handle_edit_caller_id()


def test_handle_edit_caller_id_no_caller_id_matches(
    mocker: MockerFixture,
) -> None:
    """Test handle_edit_caller_id raises when no caller ID directive found."""
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_extension",
        return_value="1001",
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_caller_id",
        return_value='"New Name" <1001>',
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.search_for_extension",
        return_value=[
            ConfigMatch(
                file_path=Path("extensions.conf"),
                line_number=5,
                matched_text="some other content",
            )
        ],
    )

    with pytest.raises(AsteriskCliError, match="No caller ID"):
        handle_edit_caller_id()


def test_handle_edit_caller_id_multiple_matches_prompts(
    mocker: MockerFixture,
) -> None:
    """Test handle_edit_caller_id with multiple caller ID matches prompts user."""
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_extension",
        return_value="1001",
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.read_caller_id",
        return_value='"New Name" <1001>',
    )
    mocker.patch(
        "asterisk_phone_management.cli.handlers.search_for_extension",
        return_value=[
            ConfigMatch(
                file_path=Path("sip.conf"),
                line_number=5,
                matched_text='callerid="Old Name 1" <1001>',
            ),
            ConfigMatch(
                file_path=Path("sip.conf"),
                line_number=10,
                matched_text='callerid="Old Name 2" <1001>',
            ),
        ],
    )
    mock_prompt = mocker.patch(
        "asterisk_phone_management.cli.handlers.prompt_select_caller_id",
    )
    mocker.patch("asterisk_phone_management.cli.handlers.edit_caller_id")

    handle_edit_caller_id()

    mock_prompt.assert_called_once()
