"""Shared Tailwind/Quasar class strings for the web interface.

Centralizing these avoids retyping the same Dracula-themed class
combinations (and hex codes) on every card, button, and input across the
page modules. Built from the shared `DRACULA` palette in
`asterisk_phone_management.core.theme` so the web UI can never drift from
the CLI's Rich theme in `core/constants.py`.
"""

from asterisk_phone_management.core.theme import DRACULA

HEADING_CLASSES: str = (
    f"text-2xl font-bold mt-8 mb-6 mx-auto text-center"
    f" text-[{DRACULA.foreground}]"
)

CARD_CLASSES: str = (
    f"items-center p-4 bg-[{DRACULA.current_line}] text-[{DRACULA.foreground}]"
    f" border border-[{DRACULA.comment}] rounded-lg shadow-md"
)
CARD_LABEL_CLASSES: str = (
    f"text-[{DRACULA.foreground}] font-medium text-center"
)
ICON_CLASSES: str = f"text-4xl mb-2 text-[{DRACULA.cyan}]"

RESULTS_CONTAINER_CLASSES: str = (
    "w-full max-w-2xl mx-auto mt-6 max-h-[500px] overflow-y-auto p-2"
    f" border border-[{DRACULA.comment}] rounded-lg bg-[{DRACULA.background}]"
)
RESULT_CARD_CLASSES: str = (
    f"w-full p-3 bg-[{DRACULA.current_line}]"
    f" border border-[{DRACULA.comment}] rounded-md"
)
ERROR_TEXT_CLASSES: str = f"text-[{DRACULA.pink}] p-2"

INPUT_CLASSES: str = f"flex-grow text-[{DRACULA.foreground}]"
INPUT_PROPS: str = "autofocus dark label-color=purple-3"

BUTTON_PROPS: str = "color=primary text-color=dark"
BUTTON_PROPS_POSITIVE: str = "color=positive text-color=dark"
BUTTON_PROPS_NEGATIVE: str = "color=negative text-color=dark"
BUTTON_CLASSES: str = "font-semibold"

LINK_CLASSES: str = (
    f"text-[{DRACULA.foreground}] hover:text-[{DRACULA.purple}]"
)
