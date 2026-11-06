"""Tests for explicit application creation and startup."""

import importlib
import tomllib
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from asterisk_phone_management import __version__
from asterisk_phone_management.api.app import create_app
from asterisk_phone_management.core.exceptions import AsteriskCliError
from asterisk_phone_management.core.settings import get_settings

APP_MODULE = "asterisk_phone_management.api.app"
PROJECT = Path(__file__).resolve().parents[2]


def test_factory_builds_independent_apps(mocker: MockerFixture) -> None:
    """Each explicit call builds an app and mounts its UI once."""
    mount = mocker.patch(f"{APP_MODULE}.mount_ui")
    first = create_app()
    second = create_app()
    assert first is not second
    assert first.version == second.version == __version__
    assert mount.call_args_list == [mocker.call(first), mocker.call(second)]
    with TestClient(first) as client:
        assert client.get("/openapi.json").status_code == 200


def test_logging_is_configured_at_startup(mocker: MockerFixture) -> None:
    """Creating the app alone does not configure logging."""
    mocker.patch(f"{APP_MODULE}.mount_ui")
    configure = mocker.patch(f"{APP_MODULE}.configure_logging")
    app = create_app()
    configure.assert_not_called()
    with TestClient(app):
        configure.assert_called_once_with()


def test_bad_auth_fails_before_mounting(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    """Invalid security settings fail before any UI registration."""
    monkeypatch.setenv("ASTERISK_CLI_WEB_AUTH", "invalid")
    get_settings.cache_clear()
    mount = mocker.patch(f"{APP_MODULE}.mount_ui")
    with pytest.raises(AsteriskCliError, match="'none' or 'basic'"):
        create_app()
    mount.assert_not_called()


def test_configured_entrypoint_loads_as_factory(mocker: MockerFixture) -> None:
    """The configured import target is a callable app factory."""
    data = tomllib.loads((PROJECT / "pyproject.toml").read_text("utf-8"))
    entrypoint = data["tool"]["fastapi"]["entrypoint"]
    module_name, name = entrypoint.split(":")
    assert callable(getattr(importlib.import_module(module_name), name))
    mocker.patch(f"{APP_MODULE}.mount_ui")
    config = uvicorn.Config(entrypoint, factory=True, log_config=None)
    config.load()
    assert config.loaded
