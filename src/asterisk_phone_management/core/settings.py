"""Typed, lazily loaded application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_sip_mode(value: object) -> object:
    """Normalize a SIP mode before checking the allowed values.

    Args:
        value: The raw setting from the environment, dotenv, or arguments.

    Returns:
        A trimmed, lowercase string, or the original non-string value
        so Pydantic can reject it rather than coercing it.
    """
    return value.strip().lower() if isinstance(value, str) else value


SipSecretMode = Annotated[
    Literal["random", "mac"], BeforeValidator(_normalize_sip_mode)
]


class Settings(BaseSettings):
    """Application configuration loaded from environment vars and dotenv."""

    model_config = SettingsConfigDict(
        env_prefix="ASTERISK_CLI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_by_name=True,
        hide_input_in_errors=True,
    )

    # Base directories
    etc_asterisk: Path = Field(
        default=Path("/etc/asterisk"), validation_alias="ASTERISK_CLI_ETC"
    )
    tftpboot: Path = Field(
        default=Path("/var/lib/tftpboot"),
        validation_alias="ASTERISK_CLI_TFTPBOOT",
    )
    # Configurable file locations
    lock_file: Path = Field(
        default_factory=lambda data: (
            data["etc_asterisk"] / ".asterisk-phone-management.lock"
        ),
    )
    call_forwarding_file: Path = Path(
        "/etc/asterisk-phone-management/call_forwarding.toml"
    )

    editor: str = Field(default="", validation_alias="EDITOR")

    # Phone SSH credentials
    phone_ssh_user: str = ""
    phone_ssh_pass: SecretStr = SecretStr("")

    # Provisioning and call forwarding
    sip_secret_mode: SipSecretMode = "random"
    forwarding_gateway: str = ""

    # Web authentication and network restrictions.
    web_auth: str = "none"
    web_user: str = ""
    web_password: SecretStr = SecretStr("")
    allowed_networks: str = ""

    @property
    def sip_conf(self) -> Path:
        """The SIP configuration path."""
        return self.etc_asterisk / "sip.conf"

    @property
    def extensions_conf(self) -> Path:
        """The dialplan configuration path."""
        return self.etc_asterisk / "extensions.conf"

    @property
    def voicemail_conf(self) -> Path:
        """The voicemail configuration path."""
        return self.etc_asterisk / "voicemail.conf"

    @property
    def xml_template(self) -> Path:
        """The phone provisioning template path."""
        return self.tftpboot / "SEP0000000.cnf.xml"

    @property
    def required_files(self) -> tuple[Path, ...]:
        """The files required by the CLI."""
        return (
            self.sip_conf,
            self.extensions_conf,
            self.voicemail_conf,
            self.xml_template,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings on first use and reuse the cached instance.

    Returns:
        The cached application settings.
    """
    return Settings()
