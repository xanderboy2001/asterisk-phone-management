"""Tests for lazy, cached application settings."""

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from pydantic import ValidationError

from asterisk_phone_management.core.settings import (
    Settings,
    get_settings,
)


@pytest.fixture(autouse=True)
def clean_settings_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[None]:
    """Keep settings tests independent of local configuration."""
    for name in tuple(os.environ):
        if name.upper().startswith("ASTERISK_CLI_"):
            monkeypatch.delenv(name)

    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()

    try:
        yield
    finally:
        get_settings.cache_clear()


def test_defaults_and_derived_paths() -> None:
    settings = Settings(_env_file=None)

    assert settings.etc_asterisk == Path("/etc/asterisk")
    assert settings.tftpboot == Path("/var/lib/tftpboot")
    assert settings.sip_conf == Path("/etc/asterisk/sip.conf")
    assert settings.extensions_conf == Path("/etc/asterisk/extensions.conf")
    assert settings.voicemail_conf == Path("/etc/asterisk/voicemail.conf")
    assert settings.xml_template == Path(
        "/var/lib/tftpboot/SEP0000000.cnf.xml"
    )
    assert settings.lock_file == Path(
        "/etc/asterisk/.asterisk-phone-management.lock"
    )
    assert settings.required_files == (
        settings.sip_conf,
        settings.extensions_conf,
        settings.voicemail_conf,
        settings.xml_template,
    )
    assert settings.call_forwarding_file == Path(
        "/etc/asterisk-phone-management/call_forwarding.toml"
    )
    assert settings.sip_secret_mode == "random"
    assert not settings.forwarding_gateway
    assert settings.web_auth == "none"
    assert not settings.allowed_networks


def test_directory_overrides_update_derived_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    etc = tmp_path / "custom-etc"
    tftp = tmp_path / "custom-tftp"

    monkeypatch.setenv("ASTERISK_CLI_ETC", str(etc))
    monkeypatch.setenv("ASTERISK_CLI_TFTPBOOT", str(tftp))

    settings = Settings(_env_file=None)

    assert settings.etc_asterisk == etc
    assert settings.tftpboot == tftp
    assert settings.sip_conf == etc / "sip.conf"
    assert settings.extensions_conf == etc / "extensions.conf"
    assert settings.voicemail_conf == etc / "voicemail.conf"
    assert settings.xml_template == tftp / "SEP0000000.cnf.xml"
    assert settings.lock_file == (etc / ".asterisk-phone-management.lock")


def test_explicit_lock_override_wins(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    lock = tmp_path / "custom.lock"
    monkeypatch.setenv("ASTERISK_CLI_LOCK_FILE", str(lock))

    assert Settings(_env_file=None).lock_file == lock


def test_dotenv_is_loaded_without_mutating_environment(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "ASTERISK_CLI_FORWARDING_GATEWAY=from_dotenv\n",
        encoding="utf-8",
    )

    assert get_settings.cache_info().currsize == 0
    assert get_settings().forwarding_gateway == "from_dotenv"
    assert "ASTERISK_CLI_FORWARDING_GATEWAY" not in os.environ


def test_environment_overrides_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "ASTERISK_CLI_FORWARDING_GATEWAY=from_dotenv\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "ASTERISK_CLI_FORWARDING_GATEWAY",
        "from_environment",
    )

    assert get_settings().forwarding_gateway == "from_environment"


def test_dotenv_can_be_disabled(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "ASTERISK_CLI_FORWARDING_GATEWAY=from_dotenv\n",
        encoding="utf-8",
    )

    assert not Settings(_env_file=None).forwarding_gateway


def test_unrelated_dotenv_keys_are_ignored(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "UNRELATED_TOOL_OPTION=value\n",
        encoding="utf-8",
    )

    assert get_settings().sip_secret_mode == "random"


def test_settings_are_cached_until_explicitly_cleared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ASTERISK_CLI_FORWARDING_GATEWAY",
        "first",
    )
    first = get_settings()

    monkeypatch.setenv(
        "ASTERISK_CLI_FORWARDING_GATEWAY",
        "second",
    )

    assert get_settings() is first
    assert get_settings().forwarding_gateway == "first"

    get_settings.cache_clear()

    assert get_settings() is not first
    assert get_settings().forwarding_gateway == "second"


@pytest.mark.parametrize("mode", ["random", "mac", "MAC", " mac ", "Random"])
def test_supported_sip_modes(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    monkeypatch.setenv("ASTERISK_CLI_SIP_SECRET_MODE", mode)

    assert Settings(_env_file=None).sip_secret_mode == mode.strip().lower()


@pytest.mark.parametrize("mode", ["invalid", "macc", "", "   ", "ran\ndom"])
def test_invalid_sip_mode_is_rejected(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setenv("ASTERISK_CLI_SIP_SECRET_MODE", mode)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_passwords_are_masked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ASTERISK_CLI_PHONE_SSH_PASS",
        "ssh-secret-sentinel",
    )
    monkeypatch.setenv(
        "ASTERISK_CLI_WEB_PASSWORD",
        "web-secret-sentinel",
    )

    settings = Settings(_env_file=None)

    assert settings.phone_ssh_pass.get_secret_value() == (
        "ssh-secret-sentinel"
    )
    assert settings.web_password.get_secret_value() == ("web-secret-sentinel")

    for representation in (
        str(settings),
        repr(settings),
        settings.model_dump_json(),
    ):
        assert "ssh-secret-sentinel" not in representation
        assert "web-secret-sentinel" not in representation


def test_missing_production_paths_do_not_prevent_settings_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing = tmp_path / "not-created"
    monkeypatch.setenv("ASTERISK_CLI_ETC", str(missing))

    settings = Settings(_env_file=None)

    assert settings.sip_conf == missing / "sip.conf"
    assert not missing.exists()
