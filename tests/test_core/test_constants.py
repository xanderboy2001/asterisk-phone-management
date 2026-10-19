"""Unit tests for the clal forwarding roseter loader."""

from pathlib import Path

from asterisk_phone_management.core.constants import (
    CallForwardingDefinition,
    load_call_forwarding_users,
)


def test_load_call_forwarding_users_missing_file(tmp_path: Path) -> None:
    """A missing roster file yields an empty list."""
    assert load_call_forwarding_users(tmp_path / "missing.toml") == []


def test_load_call_forwarding_users_reads_users(tmp_path: Path) -> None:
    """Each [[users]] table becomes a CallForwardingDefinition."""
    roster = tmp_path / "call_forwarding.toml"
    roster.write_text(
        "[[users]]\n"
        'name = "Buzz Lightyear"\n'
        'extension = "1001"\n'
        'forwarding_number = "15555550100"\n',
        encoding="utf-8",
    )
    assert load_call_forwarding_users(roster) == [
        CallForwardingDefinition(
            name="Buzz Lightyear",
            extension="1001",
            forwarding_number="15555550100",
        )
    ]


def test_load_call_forwarding_users_no_users_key(tmp_path: Path) -> None:
    """A roster file without a users table yields an empty list."""
    roster = tmp_path / "call_forwarding.toml"
    roster.write_text("", encoding="utf-8")
    assert load_call_forwarding_users(roster) == []
