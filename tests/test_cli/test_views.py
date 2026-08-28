"""Unit tests for Rich table generation and view rendering functions."""

from pytest_mock import MockerFixture
from rich.table import Table

from asterisk_phone_management.cli.views import (
    _format_duration,
    _generate_call_table,
    print_phone_table,
    view_active_calls,
)
from asterisk_phone_management.schemas.models import (
    ActiveCall,
    Phone,
    Voicemail,
)


def test_format_duration() -> None:
    assert _format_duration("45") == "00:45"
    assert _format_duration("125") == "02:05"
    assert _format_duration("3665") == "01:01:05"
    assert _format_duration("invalid") == "invalid"


def test_generate_call_table_empty() -> None:
    table = _generate_call_table([])
    assert isinstance(table, Table)
    assert table.row_count == 1


def test_generate_call_table_with_calls(
    sample_active_call: ActiveCall,
) -> None:
    table = _generate_call_table([sample_active_call])
    assert table.row_count == 1

    call_no_name = ActiveCall(
        channel="SIP/SEP112233445566-00000001",
        context="default",
        extension="1001",
        priority="1",
        state="Up",
        application="Dial",
        data="SIP/SEP112233445566",
        caller_id_num="1002",
        caller_id_name="",
        account_code="",
        ama_flags="DOCUMENTATION",
        duration="125",
        bridged_channel="",
    )
    table_no_name = _generate_call_table([call_no_name])
    assert table_no_name.row_count == 1


def test_print_phone_table_renders(
    sample_phone: Phone, sample_voicemail: Voicemail
) -> None:
    print_phone_table(sample_phone, sample_voicemail)


def test_view_active_calls_keyboard_interrupt(mocker: MockerFixture) -> None:
    mocker.patch("src.cli.views.get_active_calls", return_value=[])
    mocker.patch("src.cli.views.Live")
    mocker.patch("time.sleep", side_effect=KeyboardInterrupt)

    view_active_calls()
