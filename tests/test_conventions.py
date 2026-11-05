"""Checks that apply to every module in the package."""

import ast
import re
from pathlib import Path

PACKAGE = (
    Path(__file__).resolve().parents[1] / "src" / "asterisk_phone_management"
)


def _bare_strings(path: Path) -> list[int]:
    """Find module-level string statements other than the docstring.

    Args:
        path: The Python file to check.

    Returns:
        Line numbers of strings that do nothing at runtime.
    """
    body = ast.parse(path.read_text(encoding="utf-8")).body
    return [
        node.lineno
        for node in body[1:]
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]


def test_no_bare_module_level_strings() -> None:
    """Explanations between statements are comments, not lost strings."""
    offenders = [
        f"{path.relative_to(PACKAGE)}:{line}"
        for path in sorted(PACKAGE.rglob("*.py"))
        for line in _bare_strings(path)
    ]

    assert offenders == []


def test_no_invalid_tailwind_padding() -> None:
    """Tailwind spacing classes need a hyphen: pb-1, not pb1."""
    offenders = [
        f"{path.relative_to(PACKAGE)}:{number}"
        for path in sorted((PACKAGE / "web").rglob("*.py"))
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        )
        if re.search(r"\b[pm][trblxy]?\d+\b", line)
    ]

    assert offenders == []
