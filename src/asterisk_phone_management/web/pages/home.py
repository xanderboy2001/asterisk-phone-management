"""Home page component for Asterisk Phone Management."""

from dataclasses import dataclass

from nicegui import ui

from asterisk_phone_management.web.utils import theme
from asterisk_phone_management.web.utils.styles import (
    BUTTON_CLASSES,
    BUTTON_PROPS,
    CARD_CLASSES,
    CARD_LABEL_CLASSES,
    HEADING_CLASSES,
    ICON_CLASSES,
)


@dataclass(frozen=True)
class CardConfig:
    """Configuration for a single navigation card on the home page.

    Attributes:
        icon: Name of the Quasar icon to render.
        label: Text title displayed on the card.
        target: Route URL to navigate to when the card's button is clicked.
    """

    icon: str
    label: str
    target: str


_CARDS: tuple[CardConfig, ...] = (
    CardConfig(icon="phone", label="Search for a Phone", target="/search"),
    CardConfig(
        icon="voicemail",
        label="Reset Voicemail Password",
        target="/voicemail-reset",
    ),
    CardConfig(
        icon="restart_alt", label="Reboot Phone", target="/reboot-phone"
    ),
    CardConfig(icon="badge", label="Edit Caller ID", target="/edit-caller-id"),
    CardConfig(
        icon="phone_forwarded",
        label="Toggle Call Forwarding",
        target="/toggle-call-forwarding",
    ),
)


def _create_card(
    icon: str, card_label: str, page: str, button_label: str = "Open"
) -> None:
    """Renders an action card with an icon, label, an navigation button.

    Args:
        icon: Name of the Quasar icon to render.
        card_label: Text title for the card.
        page: Target route URL for navigation when clicked.
        button_label: Text label for the action button. Defaults to "Open".
    """
    with ui.card().classes(f"w-48 {CARD_CLASSES}"):
        ui.icon(icon).classes(ICON_CLASSES)
        ui.label(card_label).classes(CARD_LABEL_CLASSES)
        ui.button(
            text=button_label, on_click=lambda: ui.navigate.to(page)
        ).props(BUTTON_PROPS).classes(f"mt-2 {BUTTON_CLASSES}")


def register_page() -> None:
    """Register the home page route with NiceGUI."""

    @ui.page("/")
    def home_page() -> None:
        """Renders the home page view."""
        with theme.frame("Homepage"):
            ui.label("Asterisk Phone Management").classes(HEADING_CLASSES)

            with ui.row().classes("gap-4 justify-center flex-wrap"):
                for card in _CARDS:
                    _create_card(
                        icon=card.icon, card_label=card.label, page=card.target
                    )
