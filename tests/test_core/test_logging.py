"""Tests for explicit, repeatable application logging setup."""

import logging

from rich.logging import RichHandler

from asterisk_phone_management.core.constants import log
from asterisk_phone_management.core.logging import configure_logging


def test_logging_setup_is_idempotent_and_preserves_root() -> None:
    """Repeated startup adds no duplicate handler or root configuration."""
    root = logging.getLogger()
    root_handlers = root.handlers[:]
    root_level = root.level
    configure_logging()
    handlers = log.handlers[:]
    configure_logging(verbose=True)
    assert log.handlers == handlers
    assert sum(isinstance(h, RichHandler) for h in handlers) == 1
    assert log.level == logging.DEBUG
    configure_logging()
    assert log.level == logging.INFO
    assert root.handlers == root_handlers
    assert root.level == root_level
