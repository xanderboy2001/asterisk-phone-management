"""Tests for scripts/check_version.py, the semver.org version check."""

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_version.py"


def _load_script() -> ModuleType:
    """Import the script as a module, since scripts/ isn't a package.

    Returns:
        The loaded module.
    """
    spec = importlib.util.spec_from_file_location("check_version", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cv = _load_script()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0.2.0", (0, 2, 0)),
        ("10.20.30", (10, 20, 30)),
        ("1.0.0-rc.1", None),
        ("1.0.0+build.5", None),
        ("01.2.3", None),
        ("1.02.3", None),
        ("1.2", None),
        ("1.2.3.4", None),
        ("v1.2.3", None),
        ("", None),
    ],
)
def test_parse(text: str, expected: tuple[int, int, int] | None) -> None:
    """Only plain MAJOR.MINOR.PATCH without leading zeros is accepted."""
    assert cv.parse(text) == expected


def test_next_versions_reset_lower_parts() -> None:
    """Minor and major bumps reset the parts after them to zero."""
    assert cv.next_versions((1, 4, 7)) == [(1, 4, 8), (1, 5, 0), (2, 0, 0)]


@pytest.mark.parametrize("version", ["0.2.0", "0.2.1", "0.3.0", "1.0.0"])
def test_check_allows_valid_steps(version: str) -> None:
    """Staying put or taking one semver step from the latest tag is fine."""
    assert not cv.check(version, [(0, 1, 0), (0, 2, 0)], release=False)


@pytest.mark.parametrize(
    "version", ["0.2.2", "0.3.1", "0.4.0", "1.1.0", "2.0.0", "0.1.0", "0.1.5"]
)
def test_check_rejects_skips_and_going_back(version: str) -> None:
    """Skipping a number, not resetting, or going backwards is refused."""
    error = cv.check(version, [(0, 1, 0), (0, 2, 0)], release=False)
    assert "isn't a valid step from the latest release 0.2.0" in error
    assert "0.2.0, 0.2.1, 0.3.0, 1.0.0" in error


def test_check_rejects_bad_format() -> None:
    """A version that isn't MAJOR.MINOR.PATCH is refused."""
    assert "MAJOR.MINOR.PATCH" in cv.check("1.0", [], release=False)


def test_check_without_tags_accepts_any_valid_version() -> None:
    """Before the first release there's nothing to compare against."""
    assert not cv.check("0.2.0", [], release=False)
    assert not cv.check("0.2.0", [(0, 2, 0)], release=True)


def test_check_release_requires_a_bump() -> None:
    """A release must be one step after the previous release."""
    tags = [(0, 2, 0), (0, 3, 0)]
    assert not cv.check("0.3.0", tags, release=True)
    assert "Use one of: 0.2.1, 0.3.0, 1.0.0" in cv.check(
        "0.4.0", [(0, 2, 0), (0, 4, 0)], release=True
    )


def test_check_release_rejects_older_version() -> None:
    """Releasing a number lower than an existing release is refused."""
    error = cv.check("0.2.1", [(0, 2, 1), (0, 3, 0)], release=True)
    assert "latest release 0.3.0" in error


def _git(repo: Path, *args: str) -> None:
    """Run a git command in a test repository.

    Args:
        repo: The repository directory.
        *args: Arguments for git.
    """
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a git repository with a pyproject.toml and some tags.

    Returns:
        The repository directory, which is also the working directory.
    """
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.2.0"\n', encoding="utf-8"
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    for tag in ("v0.1.0", "v0.2.0", "not-a-version", "v1.0.0-rc.1"):
        _git(tmp_path, "tag", tag)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.usefixtures("repo")
def test_release_tags_ignores_other_tags() -> None:
    """Only vX.Y.Z tags count as releases."""
    assert sorted(cv.release_tags()) == [(0, 1, 0), (0, 2, 0)]


def test_main_exit_codes(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """main() returns 0 for a valid version and 1 with a message otherwise."""
    assert cv.main([]) == 0

    (repo / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.4.0"\n', encoding="utf-8"
    )
    assert cv.main([]) == 1
    assert "isn't a valid step" in capsys.readouterr().err


@pytest.mark.usefixtures("repo")
def test_main_release_needs_new_version() -> None:
    """With --release, re-releasing the latest version is refused."""
    assert cv.main(["--release"]) == 0  # 0.2.0 after 0.1.0
    _git(Path.cwd(), "tag", "v0.3.0")
    assert cv.main(["--release"]) == 1  # 0.2.0 after 0.3.0


def test_release_tags_without_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clear error is raised when git is missing."""
    monkeypatch.setattr(cv.shutil, "which", lambda _name: None)
    with pytest.raises(RuntimeError, match="git is not installed"):
        cv.release_tags()
