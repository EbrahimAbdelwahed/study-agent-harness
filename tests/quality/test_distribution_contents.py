from __future__ import annotations

import os
import re
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parents[2]
DIST_ROOT = PROJECT_ROOT / "dist"
VERSION = "0.2.0"
PRIVATE_NAME = re.compile(
    r"(?:sbobby|tutorkit|study-agent-(?:ui|platform)|vetrina|inglese|audio_to_sbobina)",
    re.IGNORECASE,
)
ABSOLUTE_USER_PATH = re.compile(r"(?:/Users/|/home/|[A-Za-z]:[\\/]Users[\\/])")
HIGH_CONFIDENCE_SECRET = re.compile(
    r"(?:"
    r"AKIA[0-9A-Z]{16}"
    r"|gh[pousr]_[A-Za-z0-9]{36,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|sk-(?:proj-)?[A-Za-z0-9_-]{20,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r")"
)


def _current_archive(suffix: str) -> Path:
    pattern = (
        f"study_agent_harness-{VERSION}-*.whl"
        if suffix == ".whl"
        else f"study_agent_harness-{VERSION}.tar.gz"
    )
    candidates = sorted(
        path
        for path in DIST_ROOT.glob(pattern)
        if path.is_file() and path.stat().st_mtime >= _source_freshness_mtime()
    )
    if len(candidates) != 1:
        if os.environ.get("STUDY_AGENT_REQUIRE_DIST") == "1":
            pytest.fail(
                f"expected exactly one current {suffix} archive in {DIST_ROOT}, "
                f"found {len(candidates)}"
            )
        pytest.skip(
            f"expected exactly one current {suffix} archive in {DIST_ROOT}, "
            f"found {len(candidates)}"
        )
    return candidates[0]


def _source_freshness_mtime() -> float:
    """Treat old local archives as absent until they post-date this checkout."""
    inputs = [
        PROJECT_ROOT / "pyproject.toml",
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "LICENSE",
        *(PROJECT_ROOT / "src/study_agent").rglob("*"),
    ]
    return max(
        path.stat().st_mtime
        for path in inputs
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix in {".py", ".md", ".typed", ".toml"}
    )


def test_current_wheel_contains_runtime_surfaces_and_no_local_material() -> None:
    archive = _current_archive(".whl")
    with zipfile.ZipFile(archive) as wheel:
        names = tuple(wheel.namelist())
        files = {name for name in names if not name.endswith("/")}

        expected_tools = {
            f"study_agent/tools/{path.name}"
            for path in (PROJECT_ROOT / "src/study_agent/tools").glob("*.py")
        }
        assert "study_agent/py.typed" in files
        assert expected_tools <= files
        assert "study_agent/operator_skill/SKILL.md" in files
        assert "study_agent/demo/fixtures/heart-valves.md" in files

        metadata_name = next(name for name in files if name.endswith(".dist-info/METADATA"))
        metadata = wheel.read(metadata_name).decode("utf-8")
        assert "Name: study-agent-harness\n" in metadata
        assert f"Version: {VERSION}\n" in metadata
        assert "License-Expression: Apache-2.0\n" in metadata
        assert any(
            name.endswith(".dist-info/licenses/LICENSE")
            or name.endswith(".dist-info/LICENSE")
            for name in files
        )

        forbidden_prefixes = ("tests/", "dev/", "docs/", ".worktrees/")
        assert not any(
            name.startswith(forbidden) for name in files for forbidden in forbidden_prefixes
        )
        credential_name = re.compile(
            r"(?:^|/)(?:\.env(?:$|[._-])|[^/]*(?:credential|secret|token|password|passwd|api[_-]?key|private[_-]?key)[^/]*)$",
            re.IGNORECASE,
        )
        assert not any(credential_name.search(name) for name in files)
        for name in files:
            if not name.endswith((".py", ".md", "/METADATA", "/SKILL.md")):
                continue
            text = wheel.read(name).decode("utf-8")
            assert not PRIVATE_NAME.search(text), name
            assert not ABSOLUTE_USER_PATH.search(text), name
            assert not HIGH_CONFIDENCE_SECRET.search(text), name


def test_current_sdist_contains_source_metadata_and_no_checkout_junk() -> None:
    archive = _current_archive(".tar.gz")
    with tarfile.open(archive, "r:gz") as source:
        names = tuple(name for name in source.getnames() if name != ".")
        assert names
        root = names[0].split("/", 1)[0]
        files = {name for name in names if not name.endswith("/")}

        assert f"{root}/LICENSE" in files
        assert f"{root}/README.md" in files
        assert f"{root}/pyproject.toml" in files
        assert f"{root}/src/study_agent/__init__.py" in files
        assert not any(
            name == f"{root}/dev" or name.startswith(f"{root}/dev/") for name in names
        )
        assert not any(
            name == f"{root}/.worktrees" or name.startswith(f"{root}/.worktrees/")
            for name in names
        )
        assert not any(name.lower().endswith(".lock") for name in files)
        duplicate_marker = re.compile(
            r"(?:\s\d+|[_-](?:copy|duplicate))\.[^/]+$", re.IGNORECASE
        )
        assert not any(duplicate_marker.search(name) for name in files)
        for member in source.getmembers():
            if not member.isfile() or not member.name.endswith(
                (".py", ".md", ".toml", "/PKG-INFO")
            ):
                continue
            extracted = source.extractfile(member)
            assert extracted is not None
            text = extracted.read().decode("utf-8")
            assert not PRIVATE_NAME.search(text), member.name
            assert not ABSOLUTE_USER_PATH.search(text), member.name
            assert not HIGH_CONFIDENCE_SECRET.search(text), member.name


def test_release_metadata_and_documentation_agree_on_version_and_license() -> None:
    metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = metadata["project"]
    assert project["version"] == VERSION
    assert project["license"] == "Apache-2.0"

    runtime = (PROJECT_ROOT / "src/study_agent/__init__.py").read_text(encoding="utf-8")
    assert f'__version__ = "{VERSION}"' in runtime
    for path in (
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "CHANGELOG.md",
        PROJECT_ROOT / "SECURITY.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert VERSION in text, f"{path} does not name the current release"
    assert "Apache License" in (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Version 2.0" in (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")


def test_maintained_release_surfaces_have_no_private_product_or_user_path_leaks() -> None:
    roots = (
        PROJECT_ROOT / "src/study_agent",
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "SECURITY.md",
        PROJECT_ROOT / "CONTRIBUTING.md",
        PROJECT_ROOT / "CODE_OF_CONDUCT.md",
        PROJECT_ROOT / "GOVERNANCE.md",
        PROJECT_ROOT / "SUPPORT.md",
        PROJECT_ROOT / "CHANGELOG.md",
        PROJECT_ROOT / "pyproject.toml",
        PROJECT_ROOT / ".github",
        PROJECT_ROOT / "docs/examples",
        PROJECT_ROOT / "docs/integrations.md",
        PROJECT_ROOT / "docs/maintainer",
        PROJECT_ROOT / "docs/reference-tutor-host.md",
    )
    violations: list[str] = []
    for root in roots:
        paths = (root,) if root.is_file() else sorted(root.rglob("*"))
        for path in paths:
            if not path.is_file() or path.is_symlink():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            relative = path.relative_to(PROJECT_ROOT)
            if PRIVATE_NAME.search(text):
                violations.append(f"{relative}: private product name")
            if ABSOLUTE_USER_PATH.search(text):
                violations.append(f"{relative}: absolute user path")
            if HIGH_CONFIDENCE_SECRET.search(text):
                violations.append(f"{relative}: high-confidence secret")
    assert violations == [], "maintained release-surface leaks:\n" + "\n".join(violations)
