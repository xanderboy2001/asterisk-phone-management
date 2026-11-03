"""Unit tests for caller ID service functions."""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from asterisk_phone_management.core.exceptions import (
    AsteriskCliError,
    FileTransactionError,
)
from asterisk_phone_management.schemas.models import ConfigMatch
from asterisk_phone_management.services.caller_id import (
    _apply_caller_id_updates,
    edit_caller_id,
)

SIP = Path("sip.conf")


def _match(line_number: int, text: str, file_path: Path = SIP) -> ConfigMatch:
    """Build a ConfigMatch as the search would.

    Args:
        line_number: 1-based line number.
        text: The stripped line text.
        file_path: The file the match came from.

    Returns:
        The match.
    """
    return ConfigMatch(
        file_path=file_path, line_number=line_number, matched_text=text
    )


def test_apply_caller_id_updates_success() -> None:
    """Only the matched line changes."""
    lines = [
        "[general]",
        "[SEP112233445566](phone)",
        'callerid="Old" <1001>',
        "secret=password",
    ]
    result = _apply_caller_id_updates(
        lines, [_match(3, 'callerid="Old" <1001>')], '"New" <1001>'
    )
    assert result == [
        "[general]",
        "[SEP112233445566](phone)",
        'callerid="New" <1001>',
        "secret=password",
    ]


def test_apply_caller_id_updates_keeps_indentation() -> None:
    """An indented callerid line stays indented."""
    lines = ['    callerid="Old" <1001>']
    result = _apply_caller_id_updates(
        lines, [_match(1, 'callerid="Old" <1001>')], '"New" <1001>'
    )
    assert result == ['    callerid="New" <1001>']


@pytest.mark.parametrize("line_number", [0, 3, 99])
def test_apply_caller_id_updates_missing_line(line_number: int) -> None:
    """A line number outside the file is refused."""
    lines = ["[general]", "callerid=test"]
    with pytest.raises(AsteriskCliError, match="no longer exists"):
        _apply_caller_id_updates(
            lines, [_match(line_number, "callerid=test")], '"New" <1001>'
        )


def test_apply_caller_id_updates_line_changed() -> None:
    """A line that no longer reads as searched is refused (F-18)."""
    lines = ["[general]", 'callerid="Someone Else" <2002>']
    with pytest.raises(AsteriskCliError, match="changed since the search"):
        _apply_caller_id_updates(
            lines, [_match(2, 'callerid="Old" <1001>')], '"New" <1001>'
        )


def test_apply_caller_id_updates_not_a_callerid_line() -> None:
    """A match that isn't a callerid= line is refused."""
    lines = ["[general]", "secret=password"]
    with pytest.raises(AsteriskCliError, match="not a callerid= line"):
        _apply_caller_id_updates(
            lines, [_match(2, "secret=password")], '"New" <1001>'
        )


def test_apply_caller_id_updates_all_or_nothing() -> None:
    """If one of several lines changed, none are updated."""
    lines = ['callerid="A" <1001>', 'callerid="Changed" <1001>']
    original = list(lines)
    with pytest.raises(AsteriskCliError):
        _apply_caller_id_updates(
            lines,
            [
                _match(1, 'callerid="A" <1001>'),
                _match(2, 'callerid="B" <1001>'),
            ],
            '"New" <1001>',
        )
    assert lines == original


@pytest.mark.usefixtures("mock_asterisk_env")
def test_edit_caller_id_success(mock_asterisk_env: dict[str, Path]) -> None:
    """Test edit_caller_id updates caller ID in sip.conf."""
    sip_conf = mock_asterisk_env["sip_conf"]
    sip_conf.write_text(
        "[general]\n[SEP112233445566](phone)\n"
        'callerid="Old" <1001>\nsecret=password\n',
        encoding="utf-8",
    )

    edit_caller_id(
        [
            ConfigMatch(
                file_path=sip_conf,
                line_number=3,
                matched_text='callerid="Old" <1001>',
            )
        ],
        '"New" <1001>',
    )

    assert sip_conf.read_text(encoding="utf-8") == (
        '[general]\n[SEP112233445566](phone)\ncallerid="New" <1001>\n'
        "secret=password\n"
    )


def test_edit_caller_id_empty_targets() -> None:
    """Test edit_caller_id returns early with empty targets."""
    edit_caller_id([], '"New" <1001>')


@pytest.mark.usefixtures("mock_asterisk_env")
def test_edit_caller_id_file_error(
    mock_asterisk_env: dict[str, Path], mocker: MockerFixture
) -> None:
    """Test edit_caller_id raises on file write error."""
    sip_conf = mock_asterisk_env["sip_conf"]
    sip_conf.write_text(
        "[general]\ncallerid=test\n",
        encoding="utf-8",
    )

    mocker.patch(
        "pathlib.Path.read_text",
        side_effect=OSError("Read error"),
    )

    with pytest.raises(FileTransactionError):
        edit_caller_id(
            [
                ConfigMatch(
                    file_path=sip_conf,
                    line_number=2,
                    matched_text="callerid=test",
                )
            ],
            '"New" <1001>',
        )


@pytest.mark.parametrize(
    "payload",
    ['"x"\n[evil](phone)\nsecret=1', '"x" <1001>;note', ""],
)
def test_edit_caller_id_rejects_injection(
    mock_asterisk_env: dict[str, Path], payload: str
) -> None:
    """Line-breaking caller IDs never reach sip.conf."""
    sip_conf = mock_asterisk_env["sip_conf"]
    before = sip_conf.read_text(encoding="utf-8")
    match = ConfigMatch(
        file_path=sip_conf,
        line_number=6,
        matched_text='callerid="John Doe" <1001>',
    )
    with pytest.raises(AsteriskCliError):
        edit_caller_id([match], payload)
    assert sip_conf.read_text(encoding="utf-8") == before


def test_edit_caller_id_rejects_other_files(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """A match from another file is refused before anything is touched."""
    sip_conf = mock_asterisk_env["sip_conf"]
    before = sip_conf.read_text(encoding="utf-8")
    match = _match(
        2,
        "exten => 1001,1,Dial(SIP/SEP112233445566,14,t)",
        mock_asterisk_env["ext_conf"],
    )
    with pytest.raises(AsteriskCliError, match=r"only be edited in sip\.conf"):
        edit_caller_id([match], '"New" <1001>')
    assert sip_conf.read_text(encoding="utf-8") == before
    assert list(mock_asterisk_env["backup_dir"].iterdir()) == []


def test_edit_caller_id_refuses_stale_line(
    mock_asterisk_env: dict[str, Path],
) -> None:
    """If sip.conf changed after the search, nothing is written (F-18)."""
    sip_conf = mock_asterisk_env["sip_conf"]
    match = _match(6, 'callerid="John Doe" <1001>', sip_conf)
    # Someone inserts a line above the match after the search.
    sip_conf.write_text(
        "; added later\n" + sip_conf.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    before = sip_conf.read_text(encoding="utf-8")

    with pytest.raises(AsteriskCliError, match="changed since the search"):
        edit_caller_id([match], '"New" <1001>')

    assert sip_conf.read_text(encoding="utf-8") == before
