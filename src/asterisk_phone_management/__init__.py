"""Asterisk Phone Management package.

Provides high-level interfaces and utilities for configuring, provisioning,
and managing Asterisk PBX phone extensions and Cisco IP endpoints.
"""

from importlib.metadata import version

# Defined once, in pyproject.toml, and read from the installed package.
__version__: str = version("asterisk-phone-management")

__all__: list[str] = [
    "__version__",
]
