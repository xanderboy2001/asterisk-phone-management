"""Unit tests for interactive CLI prompts."""

import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management.cli.prompts import (
    prompt_search_method,
    prompt_use_voicemail,
    read_caller_id,
    read_email,
    read_extension,
    read_mac_addr,
    read_name,
    read_new_password,
    read_search_query,
)
from asterisk_phone_management.core.exceptions import AsteriskCliError


def test_read_extension_success(mocker: MockerFixture) -> None:
    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = "1234"

    assert read_extension() == "1234"


def test_read_extension_cancelled(mocker: MockerFixture) -> None:
    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = None

    with pytest.raises(KeyboardInterrupt, match="Prompt cancelled by user"):
        read_extension()


def test_read_mac_addr_normalization(mocker: MockerFixture) -> None:
    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = "aa:bb:cc:dd:ee:ff"

    assert read_mac_addr() == "AABBCCDDEEFF"


def test_read_mac_addr_cancelled(mocker: MockerFixture) -> None:
    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = None
    with pytest.raises(KeyboardInterrupt, match="Prompt cancelled by user"):
        read_mac_addr()


def test_read_caller_id_formatting(mocker: MockerFixture) -> None:
    mock_text = mocker.patch("questionary.text")

    mock_text.return_value.ask.return_value = '"John Doe"'
    assert read_caller_id("1001") == '"John Doe" <1001>'

    mock_text.return_value.ask.return_value = '"John Doe" <1001>'
    assert read_caller_id("1001") == '"John Doe" <1001>'


def test_read_caller_id_cancelled(mocker: MockerFixture) -> None:
    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = None

    with pytest.raises(KeyboardInterrupt, match="Prompt cancelled by user"):
        read_caller_id("1001")


def test_read_name_success(mocker: MockerFixture) -> None:
    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = "  Jane Doe  "
    assert read_name() == "Jane Doe"


def test_read_name_cancelled(mocker: MockerFixture) -> None:
    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = None

    with pytest.raises(KeyboardInterrupt, match="Prompt cancelled by user"):
        read_name()


def test_read_email_success(mocker: MockerFixture) -> None:
    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = "  jane@example.com  "
    assert read_email() == "jane@example.com"


def test_read_email_cancelled(mocker: MockerFixture) -> None:
    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = None

    with pytest.raises(KeyboardInterrupt, match="Prompt cancelled by user"):
        read_email()


def test_read_new_password_success(mocker: MockerFixture) -> None:
    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = "1234"

    assert read_new_password("9999") == "1234"


def test_read_new_password_empty_raises_error(mocker: MockerFixture) -> None:
    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = ""

    with pytest.raises(AsteriskCliError, match="No password provided"):
        read_new_password("1001")


def test_read_search_query(mocker: MockerFixture) -> None:
    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = "test"

    assert read_search_query() == "test"


def test_read_search_query_empty_raises_error(mocker: MockerFixture) -> None:
    mock_text = mocker.patch("questionary.text")
    mock_text.return_value.ask.return_value = ""

    with pytest.raises(AsteriskCliError, match="No search query provided"):
        read_search_query()


def test_prompt_search_method_success(mocker: MockerFixture) -> None:
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = "ext"

    assert prompt_search_method() == "ext"


def test_prompt_search_method_cancelled(mocker: MockerFixture) -> None:
    mock_select = mocker.patch("questionary.select")
    mock_select.return_value.ask.return_value = None

    with pytest.raises((AsteriskCliError, KeyboardInterrupt)):
        prompt_search_method()


def test_prompt_use_voicemail_bool(mocker: MockerFixture) -> None:
    mock_confirm = mocker.patch("questionary.confirm")
    mock_confirm.return_value.ask.return_value = True

    assert prompt_use_voicemail() is True


def test_prompt_use_voicemail_cancelled(mocker: MockerFixture) -> None:
    mock_confirm = mocker.patch("questionary.confirm")
    mock_confirm.return_value.ask.side_effect = KeyboardInterrupt
    with pytest.raises((AsteriskCliError, KeyboardInterrupt)):
        prompt_use_voicemail()


def test_prompt_use_voicemail_cancelled_none(mocker: MockerFixture) -> None:
    mock_confirm = mocker.patch("questionary.confirm")
    mock_confirm.return_value.ask.return_value = None
    result = prompt_use_voicemail()
    assert result is None
