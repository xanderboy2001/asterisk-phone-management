"""Check that the project version follows Semantic Versioning 2.0.0.

The version in pyproject.toml must be a plain ``MAJOR.MINOR.PATCH`` number,
and may only move forward from the latest ``vX.Y.Z`` release tag by one of
the steps semver.org allows:

- the next patch:  0.2.0 -> 0.2.1
- the next minor:  0.2.1 -> 0.3.0  (patch reset to 0)
- the next major:  0.3.0 -> 1.0.0  (minor and patch reset to 0)

Between releases the version may also stay on the latest release. With
``--release`` it must be a new version, because the release tag for it is
being created.

Used by a pre-commit hook, by CI, and by the release workflow.
"""

import argparse
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

Version = tuple[int, int, int]

# MAJOR.MINOR.PATCH from the semver.org regular expression: no leading zeros.
# Pre-release and build labels are left out on purpose, because Python
# packaging (PEP 440) spells them differently from semver.org.
_SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")


def parse(text: str) -> Version | None:
    """Parse a ``MAJOR.MINOR.PATCH`` version.

    Args:
        text: The version text, without a leading ``v``.

    Returns:
        The three numbers, or None if the text isn't a valid version.
    """
    match = _SEMVER.fullmatch(text)
    if match is None:
        return None
    return int(match[1]), int(match[2]), int(match[3])


def show(version: Version) -> str:
    """Format a version as ``MAJOR.MINOR.PATCH``.

    Args:
        version: The version to format.

    Returns:
        The dotted version text.
    """
    return ".".join(str(part) for part in version)


def next_versions(previous: Version) -> list[Version]:
    """List the versions semver.org allows after a release.

    Args:
        previous: The latest released version.

    Returns:
        The next patch, minor, and major versions, in that order.
    """
    major, minor, patch = previous
    return [
        (major, minor, patch + 1),
        (major, minor + 1, 0),
        (major + 1, 0, 0),
    ]


def read_project_version(pyproject: Path) -> str:
    """Read ``[project] version`` from pyproject.toml.

    Args:
        pyproject: Path to pyproject.toml.

    Returns:
        The version text.
    """
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def release_tags() -> list[Version]:
    """List the versions of all ``vX.Y.Z`` tags in the repository.

    Returns:
        The tagged versions. Tags in any other format are ignored.

    Raises:
        RuntimeError: If git isn't installed.
    """
    git = shutil.which("git")
    if git is None:
        msg = "git is not installed."
        raise RuntimeError(msg)
    result = subprocess.run(
        [git, "tag", "--list", "v*"],
        capture_output=True,
        text=True,
        check=True,
    )
    versions = (
        parse(name.removeprefix("v")) for name in result.stdout.split()
    )
    return [version for version in versions if version is not None]


def check(version_text: str, tags: list[Version], *, release: bool) -> str:
    """Check a version against semver.org and the existing release tags.

    Args:
        version_text: The version from pyproject.toml.
        tags: Versions that already have a release tag.
        release: True when checking a release being tagged now.

    Returns:
        An error message, or an empty string if the version is valid.
    """
    version = parse(version_text)
    if version is None:
        return (
            f"Version {version_text!r} in pyproject.toml must be "
            "MAJOR.MINOR.PATCH with no leading zeros, e.g. 1.4.0 "
            "(https://semver.org)."
        )

    if release:
        # The tag for this version is the one being released, so compare
        # with the release before it.
        earlier = [tag for tag in tags if tag != version]
        if not earlier:
            return ""
        previous = max(earlier)
        allowed = next_versions(previous)
    else:
        if not tags:
            return ""
        previous = max(tags)
        allowed = [previous, *next_versions(previous)]

    if version in allowed:
        return ""
    return (
        f"Version {show(version)} isn't a valid step from the latest "
        f"release {show(previous)}. Use one of: "
        f"{', '.join(show(option) for option in allowed)}."
    )


def main(argv: list[str] | None = None) -> int:
    """Run the check from the command line.

    Args:
        argv: Command-line arguments. Defaults to ``sys.argv[1:]``.

    Returns:
        0 if the version is valid, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--release",
        action="store_true",
        help="require a new version (used when a release tag is pushed)",
    )
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="path to pyproject.toml (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    error = check(
        read_project_version(args.pyproject),
        release_tags(),
        release=args.release,
    )
    if error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
