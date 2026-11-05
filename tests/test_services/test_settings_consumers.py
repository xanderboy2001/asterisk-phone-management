"""Regression tests for services that resolve settings at call time."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management.core.exceptions import AsteriskCliError
from asterisk_phone_management.core.settings import Settings
from asterisk_phone_management.schemas.models import ConfigMatch
from asterisk_phone_management.services import caller_id, voicemail


def test_caller_id_uses_current_settings(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """Changing the settings provider changes which SIP file is accepted."""
    provider = mocker.patch.object(caller_id, "get_settings")
    previous: Path | None = None
    for directory in (tmp_path / "first", tmp_path / "second"):
        settings = Settings.model_construct(etc_asterisk=directory)
        provider.return_value = settings
        match = ConfigMatch(
            file_path=settings.sip_conf,
            line_number=1,
            matched_text='callerid="Old" <1001>',
        )
        caller_id._check_target_file(match)
        if previous is not None:
            with pytest.raises(AsteriskCliError, match="only be edited"):
                caller_id._check_target_file(
                    ConfigMatch(
                        file_path=previous,
                        line_number=1,
                        matched_text=match.matched_text,
                    )
                )
        previous = settings.sip_conf


def test_voicemail_uses_current_settings(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """Each reset writes to the current configured voicemail file."""
    provider = mocker.patch.object(voicemail, "get_settings")
    search = mocker.patch.object(voicemail, "search_for_extension")
    paths: list[Path] = []
    for directory in (tmp_path / "first", tmp_path / "second"):
        directory.mkdir()
        settings = Settings.model_construct(etc_asterisk=directory)
        provider.return_value = settings
        path = settings.voicemail_conf
        path.write_text("1001 = 1234, Test\n", encoding="utf-8")
        search.return_value = [
            ConfigMatch(
                file_path=path,
                line_number=1,
                matched_text="1001 = 1234, Test",
            )
        ]
        voicemail.reset_vm_password("1001", "5678")
        assert path.read_text(encoding="utf-8") == "1001 = 5678, Test\n"
        paths.append(path)
    assert paths[0].read_text(encoding="utf-8") == "1001 = 5678, Test\n"
    assert provider.call_count == 2
