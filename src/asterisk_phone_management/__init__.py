"""Asterisk Phone Management package.

Provides high-level interfaces and utilities for configuring, provisioning,
and managing Asterisk PBX phone extensions and Cisco IP endpoints.
"""

from asterisk_phone_management.main import main

# Package metadata
__version__ = "0.1.0"


__all__: list[str] = [
    "__version__",
    "main",
]
