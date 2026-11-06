"""Shared pytest fixtures, mock environments, and test data generators."""

import logging
import os
from collections.abc import Generator
from pathlib import Path

import pytest

from asterisk_phone_management.core.settings import get_settings
from asterisk_phone_management.schemas.models import (
    ActiveCall,
    ConfigMatch,
    Phone,
    Voicemail,
)


@pytest.fixture(autouse=True)
def isolated_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[None]:
    """Isolate environment, dotenv, settings cache, and logger state.

    Yields:
        Control to a test with no production configuration loaded.
    """
    for name in tuple(os.environ):
        if name.upper().startswith("ASTERISK_CLI_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ASTERISK_CLI_LOCK_FILE", str(tmp_path / "config.lock"))
    get_settings.cache_clear()
    logger = logging.getLogger("Asterisk Phone Management")
    handlers = logger.handlers[:]
    level = logger.level
    try:
        yield
    finally:
        get_settings.cache_clear()
        for handler in logger.handlers[:]:
            if handler not in handlers:
                logger.removeHandler(handler)
                handler.close()
        logger.setLevel(level)


@pytest.fixture
def mock_asterisk_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[dict[str, Path]]:
    """Create a temporary Asterisk configuration and TFTP directory structure.

    Args:
        tmp_path: Pytest temporary directory path.
        monkeypatch: Pytest monkeypatch fixture.

    Yields:
        Dictionary containing paths to the isolated configuration files.
    """
    etc_dir: Path = tmp_path / "etc" / "asterisk"
    tftp_dir: Path = tmp_path / "var" / "lib" / "tftpboot"
    backup_dir: Path = etc_dir / "backup"

    etc_dir.mkdir(parents=True, exist_ok=True)
    tftp_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    sip_conf: Path = etc_dir / "sip.conf"
    ext_conf: Path = etc_dir / "extensions.conf"
    vm_conf: Path = etc_dir / "voicemail.conf"
    xml_template: Path = tftp_dir / "SEP0000000.cnf.xml"

    sip_conf.write_text(
        "[general]\n\n[SEP112233445566](phone)\nauthname=SEP112233445566\n"
        'secret=SEP112233445566\ncallerid="John Doe" <1001>\nmailbox=1001@default\n',
        encoding="utf-8",
    )
    ext_conf.write_text(
        "[default]\nexten => 1001,1,Dial(SIP/SEP112233445566,14,t)\n"
        "exten => 1001,n,Voicemail(1001,u)\n",
        encoding="utf-8",
    )
    vm_conf.write_text(
        "[default]\n1001 = 1234, John Doe, john@example.com,,attach=yes|delete=1\n",
        encoding="utf-8",
    )
    xml_template.write_text(
        "<device><name>--SEPMAC--</name><featureLabel>--EXTENNUMBER--</featureLabel>"
        "<authPassword>--SIPSECRET--</authPassword></device>\n",
        encoding="utf-8",
    )

    existing_xml: Path = tftp_dir / "SEP112233445566.cnf.xml"
    existing_xml.write_text(
        "<device><name>SEP112233445566</name><featureLabel>1001</featureLabel></device>\n",
        encoding="utf-8",
    )

    lock_file: Path = etc_dir / ".asterisk-phone-management.lock"

    monkeypatch.setenv("ASTERISK_CLI_ETC", str(etc_dir))
    monkeypatch.setenv("ASTERISK_CLI_TFTPBOOT", str(tftp_dir))
    monkeypatch.setenv("ASTERISK_CLI_LOCK_FILE", str(lock_file))
    get_settings.cache_clear()
    yield {
        "etc_dir": etc_dir,
        "tftp_dir": tftp_dir,
        "backup_dir": backup_dir,
        "sip_conf": sip_conf,
        "ext_conf": ext_conf,
        "vm_conf": vm_conf,
        "xml_template": xml_template,
        "existing_xml": existing_xml,
        "lock_file": lock_file,
    }


@pytest.fixture
def sample_phone() -> Phone:
    """Fixture providing a standard valid Phone model.

    Returns:
        Phone domain model instance.
    """
    return Phone(
        extension="2002",
        mac_address="AABBCCDDEEFF",
        caller_id='"Jane Doe" <2002>',
    )


@pytest.fixture
def sample_voicemail() -> Voicemail:
    """Fixture providing a standard valid Voicemail model.

    Returns:
        Voicemail domain model instance.
    """
    return Voicemail(
        name="Jane Doe",
        email="jane@example.com",
    )


@pytest.fixture
def sample_config_match(tmp_path: Path) -> ConfigMatch:
    """Fixture providing a dummy ConfigMatch instance.

    Args:
        tmp_path: Pytest temporary directory path.

    Returns:
        ConfigMatch dataclass instance.
    """
    return ConfigMatch(
        file_path=tmp_path / "extensions.conf",
        line_number=5,
        matched_text="exten => 1001,1,Dial(SIP/SEP112233445566,14,t)",
    )


@pytest.fixture
def sample_active_call() -> ActiveCall:
    """Fixture providing a populated ActiveCall dataclass.

    Returns:
        ActiveCall instance.
    """
    return ActiveCall(
        channel="SIP/SEP112233445566-00000001",
        context="default",
        extension="1001",
        priority="1",
        state="Up",
        application="Dial",
        data="SIP/SEP112233445566",
        caller_id_num="1002",
        caller_id_name="Alice",
        account_code="",
        ama_flags="DOCUMENTATION",
        duration="125",
        bridged_channel="SIP/SEPAABBCCDDEEFF-00000002",
    )
