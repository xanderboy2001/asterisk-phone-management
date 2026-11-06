"""Import-side-effect regressions for configuration and application startup."""

import ast
import os
import subprocess
import sys
from pathlib import Path


def test_imports_do_not_load_settings_or_mount_ui(tmp_path: Path) -> None:
    """A fresh interpreter can import the app beside an invalid dotenv."""
    (tmp_path / ".env").write_text(
        "ASTERISK_CLI_SIP_SECRET_MODE=invalid\n"
        "ASTERISK_CLI_IMPORT_SENTINEL=must-not-enter-environment\n",
        encoding="utf-8",
    )
    source = Path(__file__).resolve().parents[2] / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        (str(source), env.get("PYTHONPATH", ""))
    )
    code = """
import importlib
import logging
import os
from unittest.mock import patch

# Preload third-party UI modules so their own imports are not attributed
# to the application. Neither application import may initialize settings.
import nicegui

root = logging.getLogger()
handlers = root.handlers[:]
level = root.level
with (
    patch('dotenv.load_dotenv') as dotenv,
    patch('logging.basicConfig') as logging_setup,
    patch('nicegui.ui.run_with') as mount,
):
    importlib.import_module('asterisk_phone_management.core.constants')
    importlib.import_module('asterisk_phone_management.api.app')
    dotenv.assert_not_called()
    logging_setup.assert_not_called()
    mount.assert_not_called()
from asterisk_phone_management.core.settings import get_settings
assert get_settings.cache_info().currsize == 0
assert root.handlers == handlers
assert root.level == level
assert 'ASTERISK_CLI_IMPORT_SENTINEL' not in os.environ
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_consumers_do_not_import_configuration_snapshots() -> None:
    """Configurable values cannot be copied from the constants module."""
    package = Path(__file__).resolve().parents[2] / "src"
    legacy = {
        "ETC_ASTERISK",
        "TFTPBOOT",
        "SIP_CONF",
        "EXTENSIONS_CONF",
        "VOICEMAIL_CONF",
        "XML_TEMPLATE",
        "LOCK_FILE",
        "REQUIRED_FILES",
        "PHONE_SSH_USER",
        "PHONE_SSH_PASS",
        "SIP_SECRET_MODE",
        "FORWARDING_GATEWAY",
        "CALL_FORWARDING_USERS",
        "CALL_FORWARDING_FILE",
    }
    offenders = []
    for path in package.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text("utf-8"))):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "asterisk_phone_management.core.constants"
            ):
                offenders.extend(
                    f"{path.name}:{alias.name}"
                    for alias in node.names
                    if alias.name in legacy
                )
    assert offenders == []
