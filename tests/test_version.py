"""Tests for the single source of the package version (F-23)."""

from importlib.metadata import version

from asterisk_phone_management import __version__
from asterisk_phone_management.api.app import app


def test_version_comes_from_package_metadata() -> None:
    """__version__ is the version installed from pyproject.toml."""
    assert __version__ == version("asterisk-phone-management")


def test_api_reports_package_version() -> None:
    """The API docs show the same version as the package."""
    assert app.version == __version__
