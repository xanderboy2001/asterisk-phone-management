"""Shared building blocks for the web interface.

Modules:
    errors: Report unexpected errors in page handlers.
    inputs: Styled input widgets with built-in validation.
    menu: The navigation menu.
    reload: Reload Asterisk after a change made in the web UI.
    styles: Shared Tailwind and Quasar class strings.
    theme: The page frame and Dracula colour theme.
    to_nicegui_validation: Adapt validator results for NiceGUI inputs.

Import the modules directly, for example
``from asterisk_phone_management.web.utils import theme``. Nothing is
re-exported here, so importing one module doesn't load the others.
"""
