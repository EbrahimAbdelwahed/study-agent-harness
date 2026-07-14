from __future__ import annotations

from pathlib import Path

from study_agent.adapters.filesystem.repository_target import (
    RepositoryTargetInspectionCode,
    initialize_repository_target,
    inspect_repository_target,
    resolve_repository_target,
)
from study_agent.repository_config import (
    EMPTY_CONFIG,
    LocalRepositoryConfig,
    ModelAdapterConfig,
)


def _different_config() -> LocalRepositoryConfig:
    return LocalRepositoryConfig(model=ModelAdapterConfig("fixture-adapter"))


def _tree_snapshot(root: Path) -> tuple[tuple[str, int, int], ...]:
    return tuple(
        (str(path.relative_to(root)), path.stat().st_mode, path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
    )


def test_inspection_reports_absent_without_creating_the_target(tmp_path: Path) -> None:
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    target = resolve_repository_target(trusted_root, "nested/repository")
    before = _tree_snapshot(trusted_root)

    result = inspect_repository_target(target, EMPTY_CONFIG)

    assert result.code is RepositoryTargetInspectionCode.ABSENT
    assert result.paths.root == trusted_root / "nested" / "repository"
    assert _tree_snapshot(trusted_root) == before


def test_inspection_reports_only_exact_config_and_layout_as_compatible(
    tmp_path: Path,
) -> None:
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    initialized = initialize_repository_target(
        resolve_repository_target(trusted_root, "repository"), EMPTY_CONFIG
    )
    target = resolve_repository_target(trusted_root, "repository")
    before = _tree_snapshot(initialized.root)

    compatible = inspect_repository_target(target, EMPTY_CONFIG)
    wrong_config = inspect_repository_target(target, _different_config())

    assert compatible.code is RepositoryTargetInspectionCode.COMPATIBLE
    assert compatible.observation is not None
    assert compatible.paths == initialized
    assert wrong_config.code is RepositoryTargetInspectionCode.CONFLICT
    assert _tree_snapshot(initialized.root) == before
    compatible.observation.close()


def test_inspection_reports_incompatible_layout_as_stable_conflict(
    tmp_path: Path,
) -> None:
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    paths = initialize_repository_target(
        resolve_repository_target(trusted_root, "repository"), EMPTY_CONFIG
    )
    paths.exports.rmdir()
    paths.exports.write_text("not a directory", encoding="utf-8")
    target = resolve_repository_target(trusted_root, "repository")
    before = _tree_snapshot(paths.root)

    first = inspect_repository_target(target, EMPTY_CONFIG)
    second = inspect_repository_target(target, EMPTY_CONFIG)

    assert first.code is RepositoryTargetInspectionCode.CONFLICT
    assert second.code is RepositoryTargetInspectionCode.CONFLICT
    assert _tree_snapshot(paths.root) == before


def test_inspection_rejects_a_target_that_appeared_after_resolution(
    tmp_path: Path,
) -> None:
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    stale_absent = resolve_repository_target(trusted_root, "repository")
    paths = initialize_repository_target(
        resolve_repository_target(trusted_root, "repository"), EMPTY_CONFIG
    )
    before = _tree_snapshot(paths.root)

    result = inspect_repository_target(stale_absent, EMPTY_CONFIG)

    assert result.code is RepositoryTargetInspectionCode.CONFLICT
    assert _tree_snapshot(paths.root) == before


def test_inspection_rejects_rebound_existing_target_without_following_it(
    tmp_path: Path,
) -> None:
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    paths = initialize_repository_target(
        resolve_repository_target(trusted_root, "repository"), EMPTY_CONFIG
    )
    stale_target = resolve_repository_target(trusted_root, "repository")
    original = trusted_root / "original"
    paths.root.rename(original)
    replacement = trusted_root / "repository"
    replacement.mkdir()
    marker = replacement / "do-not-read-or-change.txt"
    marker.write_text("preserve", encoding="utf-8")

    result = inspect_repository_target(stale_target, EMPTY_CONFIG)

    assert result.code is RepositoryTargetInspectionCode.CONFLICT
    assert marker.read_text(encoding="utf-8") == "preserve"
    assert original.is_dir()
