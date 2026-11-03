"""Apply web UI changes to the running Asterisk server."""

from nicegui import ui

from asterisk_phone_management.core.constants import log
from asterisk_phone_management.core.exceptions import AsteriskCliError
from asterisk_phone_management.services import device_actions
from asterisk_phone_management.services.device_actions import AsteriskModule

_RELOAD_HINT = "Run Reload Asterisk from the CLI to apply it."


def reload_after_change(module: AsteriskModule) -> None:
    """Reload one Asterisk module after a web change was saved.

    The change is already written to the config file, so a failed reload
    is reported as a warning, never as a failed save, and nothing is
    rolled back.

    Args:
        module: The module whose config file was changed.
    """
    try:
        device_actions.reload_asterisk_module(
            command=module.command, friendly_name=module.name
        )
    except AsteriskCliError as e:
        log.warning("Change saved, but %s didn't reload: %s", module.name, e)
        ui.notify(
            f"Saved, but Asterisk couldn't reload the {module.name}. "
            f"{e!s} {_RELOAD_HINT}",
            type="warning",
            multi_line=True,
            textColor="dark",
        )
        return
    except Exception:  # ruff: ignore[blind-except] - last-resort handler
        log.exception("Unexpected error reloading %s", module.name)
        ui.notify(
            f"Saved, but reloading the {module.name} failed unexpectedly. "
            f"{_RELOAD_HINT}",
            type="warning",
            multi_line=True,
            textColor="dark",
        )
        return
    ui.notify(
        f"Asterisk reloaded the {module.name}.",
        type="positive",
        textColor="dark",
    )
