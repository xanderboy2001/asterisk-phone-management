"""Logging setup invoked only by application entry points."""

import logging

from rich.logging import RichHandler

from asterisk_phone_management.core.constants import console, log


def configure_logging(*, verbose: bool = False) -> None:
    """Configure the application logger without replacing host handlers.

    Args:
        verbose: Enable debug output when true.
    """
    if not any(isinstance(handler, RichHandler) for handler in log.handlers):
        handler = RichHandler(
            console=console, rich_tracebacks=True, markup=True
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(handler)
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
