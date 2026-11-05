"""Test for the layout of the web package."""

import importlib
import pkgutil

from asterisk_phone_management.web import pages


def test_web_utils_is_a_regular_package() -> None:
    """web.utils has an __init__.py rather than being a namespace package."""
    utils = importlib.import_module("asterisk_phone_management.web.utils")

    assert utils.__file__ is not None


def test_pages_package_exports_every_page() -> None:
    """Every page module is listed in web.pages.__all__, and nothing else."""
    page_modules = {
        module.name for module in pkgutil.iter_modules(pages.__path__)
    }

    assert set(pages.__all__) == page_modules
