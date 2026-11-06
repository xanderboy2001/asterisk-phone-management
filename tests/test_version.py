"""Tests for the single source of the package version (F-23)."""

from importlib.metadata import version

from pytest_mock import MockerFixture

from asterisk_phone_management import __version__
from asterisk_phone_management.api.app import create_app


def test_version_comes_from_package_metadata() -> None:
    """__version__ is the version installed from pyproject.toml."""
    assert __version__ == version("asterisk-phone-management")


def test_api_reports_package_version(mocker: MockerFixture) -> None:
    """The API docs show the same version as the package."""
    mocker.patch("asterisk_phone_management.api.app.mount_ui")
    assert create_app().version == __version__
