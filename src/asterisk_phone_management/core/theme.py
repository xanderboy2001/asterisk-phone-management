"""Dracula color palette, shared by the CLI (Rich) and web (NiceGUI) UIs.

This is the single source of truth for every Dracula hex value used in the
project. Change a color here and both frontends pick it up — nothing else
should hardcode a Dracula hex code.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class _Dracula:
    """Hex values for the Dracula color specification."""

    background: str = "#282a36"
    current_line: str = "#44475a"
    foreground: str = "#f8f8f2"
    comment: str = "#6272a4"
    cyan: str = "#8be9fd"
    green: str = "#50fa7b"
    orange: str = "#ffb86c"
    pink: str = "#ff79c6"
    purple: str = "#bd93f9"
    red: str = "#ff5555"
    yellow: str = "#f1fa8c"


DRACULA = _Dracula()
