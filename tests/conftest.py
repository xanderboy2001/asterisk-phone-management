"""Shared pytest fixtures, mock environments, and test data generators."""

from collections.abc import Generator
from pathlib import Path

import pytest

from src.schemas.models import ActiveCall, ConfigMatch, Phone, Voicemail


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
        'secret=SEP112233445566\ncaller_id="John Doe" <1001>\nmailbox=1001@default\n',
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
        "<device><name>--SEPMAC--</name><featureLabel>--EXTENNUMBER--</featureLabel></device>\n",
        encoding="utf-8",
    )

    existing_xml: Path = tftp_dir / "SEP112233445566.cnf.xml"
    existing_xml.write_text(
        "<device><name>SEP112233445566</name><featureLabel>1001</featureLabel></device>\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("src.core.globals.ETC_ASTERISK", etc_dir)
    monkeypatch.setattr("src.core.globals.TFTPBOOT", tftp_dir)
    monkeypatch.setattr("src.core.globals.SIP_CONF", sip_conf)
    monkeypatch.setattr("src.core.globals.EXTENSIONS_CONF", ext_conf)
    monkeypatch.setattr("src.core.globals.VOICEMAIL_CONF", vm_conf)
    monkeypatch.setattr("src.core.globals.XML_TEMPLATE", xml_template)
    monkeypatch.setattr(
        "src.core.globals.REQUIRED_FILES",
        (sip_conf, ext_conf, vm_conf, xml_template),
    )

    monkeypatch.setattr("src.services.search.SIP_CONF", sip_conf)
    monkeypatch.setattr("src.services.search.EXTENSIONS_CONF", ext_conf)
    monkeypatch.setattr("src.services.search.VOICEMAIL_CONF", vm_conf)
    monkeypatch.setattr("src.services.search.TFTPBOOT", tftp_dir)

    monkeypatch.setattr("src.services.provisioning.SIP_CONF", sip_conf)
    monkeypatch.setattr("src.services.provisioning.EXTENSIONS_CONF", ext_conf)
    monkeypatch.setattr("src.services.provisioning.VOICEMAIL_CONF", vm_conf)
    monkeypatch.setattr("src.services.provisioning.TFTPBOOT", tftp_dir)
    monkeypatch.setattr("src.services.provisioning.XML_TEMPLATE", xml_template)

    monkeypatch.setattr("src.services.voicemail.VOICEMAIL_CONF", vm_conf)
    monkeypatch.setattr("src.edit_files.SIP_CONF", sip_conf)
    monkeypatch.setattr("src.edit_files.EXTENSIONS_CONF", ext_conf)
    monkeypatch.setattr("src.edit_files.VOICEMAIL_CONF", vm_conf)
    monkeypatch.setattr("src.helpers.TFTPBOOT", tftp_dir)

    yield {
        "etc_dir": etc_dir,
        "tftp_dir": tftp_dir,
        "backup_dir": backup_dir,
        "sip_conf": sip_conf,
        "ext_conf": ext_conf,
        "vm_conf": vm_conf,
        "xml_template": xml_template,
        "existing_xml": existing_xml,
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
