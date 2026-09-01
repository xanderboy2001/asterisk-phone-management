from collections.abc import Callable

from nicegui import ui
from nicegui.elements.input import Input

from asterisk_phone_management.core.validators import (
    validate_extension,
    validate_mac_addr,
)
from asterisk_phone_management.web.utils.styles import (
    INPUT_CLASSES,
    INPUT_PROPS,
)
from asterisk_phone_management.web.utils.to_nicegui_validation import (
    to_nicegui_validation,
)


def styled_input(
    label: str,
    placeholder: str = "",
    validation: Callable[[str], str | None] | None = None,
) -> Input:
    return (
        ui.input(label=label, placeholder=placeholder, validation=validation)
        .classes(INPUT_CLASSES)
        .props(INPUT_PROPS)
    )


def extension_input(
    label: str = "Enter an Extension",
    placeholder: str = "e.g., 1234",
):
    return styled_input(
        label=label,
        placeholder=placeholder,
        validation=lambda v: to_nicegui_validation(
            validate_extension(v) if v else True
        ),
    )


def mac_address_input(
    label: str = "Enter a MAC Address",
    placeholder: str = "e.g., AABBCCDDEEFF, AA:BB:CC:DD:EE:FF",
):
    return styled_input(
        label=label,
        placeholder=placeholder,
        validation=lambda v: to_nicegui_validation(
            validate_mac_addr(v) if v else True
        ),
    )


def caller_id_input(
    label: str = "Enter a Caller ID",
    placeholder: str = "e.g., John Smith",
):
    return styled_input(
        label=label,
        placeholder=placeholder,
    )
