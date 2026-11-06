"""Unit tests for searching via API."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from asterisk_phone_management.api.app import create_app
from asterisk_phone_management.schemas.models import ConfigMatch


@pytest.fixture
def client(mocker: MockerFixture) -> TestClient:
    """Build the API without mounting the global NiceGUI app.

    Returns:
        An isolated API test client.
    """
    mocker.patch("asterisk_phone_management.api.app.mount_ui")
    return TestClient(create_app())


@patch("asterisk_phone_management.api.routes.search.validate_extension")
@patch("asterisk_phone_management.api.routes.search.search_for_extension")
def test_search_extension_success(
    mock_search: MagicMock, mock_validate: MagicMock, client: TestClient
) -> None:
    mock_validate.return_value = True
    mock_search.return_value = [
        ConfigMatch(
            file_path=Path("/etc/asterisk/sip.conf"),
            line_number=10,
            matched_text="[1234]",
        )
    ]

    response = client.get("/api/v1/search/extension/1234")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["file_path"] == "/etc/asterisk/sip.conf"
    assert data[0]["line_number"] == 10
    assert data[0]["matched_text"] == "[1234]"


@patch("asterisk_phone_management.api.routes.search.validate_extension")
@patch("asterisk_phone_management.api.routes.search.search_for_extension")
def test_search_extension_validation_error(
    mock_search: MagicMock, mock_validate: MagicMock, client: TestClient
) -> None:
    mock_validate.return_value = "Invalid extension format."
    mock_search.return_value = []

    response = client.get("/api/v1/search/extension/1234")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid extension format."


@patch("asterisk_phone_management.api.routes.search.validate_extension")
@patch("asterisk_phone_management.api.routes.search.search_for_extension")
def test_search_extension_not_found(
    mock_search: MagicMock, mock_validate: MagicMock, client: TestClient
) -> None:
    mock_validate.return_value = True
    mock_search.return_value = []

    response = client.get("/api/v1/search/extension/1234")

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "No references to extension 1234 were found."
    )


@patch("asterisk_phone_management.api.routes.search.validate_mac_addr")
@patch("asterisk_phone_management.api.routes.search.search_for_mac_address")
def test_search_mac_addr_success(
    mock_search: MagicMock, mock_validate: MagicMock, client: TestClient
) -> None:
    mock_validate.return_value = True
    mock_search.return_value = [
        ConfigMatch(
            file_path=Path("/etc/asterisk/sip.conf"),
            line_number=10,
            matched_text="[SEPAABBCCDDEEFF](phone)",
        )
    ]

    response = client.get("/api/v1/search/mac_address/AABBCCDDEEFF")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["file_path"] == "/etc/asterisk/sip.conf"
    assert data[0]["line_number"] == 10
    assert data[0]["matched_text"] == "[SEPAABBCCDDEEFF](phone)"


@patch("asterisk_phone_management.api.routes.search.search_for_mac_address")
def test_search_mac_addr_normalizes_input(
    mock_search: MagicMock, client: TestClient
) -> None:
    """A lowercase, colon-separated MAC is searched in normalized form."""
    mock_search.return_value = [
        ConfigMatch(
            file_path=Path("/etc/asterisk/sip.conf"),
            line_number=3,
            matched_text="[SEPAABBCCDDEEFF](phone)",
        )
    ]
    response = client.get("/api/v1/search/mac_address/aa:bb:cc:dd:ee:ff")
    assert response.status_code == 200
    mock_search.assert_called_once_with("AABBCCDDEEFF")


@patch("asterisk_phone_management.api.routes.search.validate_mac_addr")
@patch("asterisk_phone_management.api.routes.search.search_for_mac_address")
def test_search_mac_addr_validation_error(
    mock_search: MagicMock, mock_validate: MagicMock, client: TestClient
) -> None:
    mock_validate.return_value = "Invalid mac_addr format."
    mock_search.return_value = []

    response = client.get("/api/v1/search/mac_address/AABBCCDDEEFF")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid mac_addr format."


@patch("asterisk_phone_management.api.routes.search.validate_mac_addr")
@patch("asterisk_phone_management.api.routes.search.search_for_mac_address")
def test_search_mac_addr_not_found(
    mock_search: MagicMock, mock_validate: MagicMock, client: TestClient
) -> None:
    mock_validate.return_value = True
    mock_search.return_value = []

    response = client.get("/api/v1/search/mac_address/AABBCCDDEEFF")

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "No references to MAC address AABBCCDDEEFF were found."
    )


@patch("asterisk_phone_management.api.routes.search.search_for_caller_id")
def test_search_caller_id_success(
    mock_search: MagicMock, client: TestClient
) -> None:
    mock_search.return_value = [
        ConfigMatch(
            file_path=Path("/etc/asterisk/sip.conf"),
            line_number=10,
            matched_text='callerid="John Smith" <1234>\n',
        )
    ]

    response = client.get("/api/v1/search/caller_id/john")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["file_path"] == "/etc/asterisk/sip.conf"
    assert data[0]["line_number"] == 10
    assert data[0]["matched_text"] == 'callerid="John Smith" <1234>\n'


@patch("asterisk_phone_management.api.routes.search.search_for_caller_id")
def test_search_caller_id_not_found(
    mock_search: MagicMock, client: TestClient
) -> None:
    mock_search.return_value = []

    response = client.get("/api/v1/search/caller_id/AABBCCDDEEFF")

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "No references to caller ID AABBCCDDEEFF were found."
    )
