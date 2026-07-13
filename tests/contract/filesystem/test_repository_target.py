from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from study_agent.adapters.filesystem import (
    RepositoryTargetError,
    ResolvedRepositoryTarget,
    initialize_repository_target,
    resolve_explicit_repository_target,
    resolve_repository_target,
)
from study_agent.repository_config import (
    CONFIG_FILENAME,
    EMPTY_CONFIG,
    LocalRepositoryConfig,
    ModelAdapterConfig,
)


def _different_config() -> LocalRepositoryConfig:
    return LocalRepositoryConfig(ModelAdapterConfig("fixture-adapter"))


def test_resolution_is_read_only_and_retains_lexical_absent_tail(tmp_path: Path) -> None:
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    existing = trusted_root / "existing"
    existing.mkdir()
    before = tuple(trusted_root.rglob("*"))

    target = resolve_repository_target(trusted_root, "existing/missing/repository")

    assert target.trusted_root == trusted_root
    assert target.relative_parts == ("existing", "missing", "repository")
    assert target.existing_parts == ("existing",)
    assert target.missing_parts == ("missing", "repository")
    assert target.existing_prefix_identities == (
        (existing.stat().st_dev, existing.stat().st_ino),
    )
    assert target.root == trusted_root / "existing" / "missing" / "repository"
    assert target.exists is False
    assert tuple(trusted_root.rglob("*")) == before


def test_resolution_records_all_existing_directory_identities(tmp_path: Path) -> None:
    trusted_root = tmp_path / "trusted"
    repository = trusted_root / "nested" / "repository"
    repository.mkdir(parents=True)

    target = resolve_repository_target(trusted_root, "nested/repository")

    assert target.exists is True
    assert target.missing_parts == ()
    assert target.existing_prefix_identities == tuple(
        (path.stat().st_dev, path.stat().st_ino)
        for path in (trusted_root / "nested", repository)
    )


@pytest.mark.parametrize(
    "unsafe_path",
    (
        "",
        ".",
        "..",
        "nested/./repository",
        "nested/../repository",
        "/absolute/repository",
        "nested\\repository",
        "C:/repository",
        "nested//repository",
        "repository ",
        "CON",
        "bad\x00name",
    ),
)
def test_resolution_rejects_nonportable_or_traversing_tails(
    tmp_path: Path, unsafe_path: str
) -> None:
    with pytest.raises(RepositoryTargetError, match="portable relative path"):
        resolve_repository_target(tmp_path, unsafe_path)


@pytest.mark.parametrize("kind", ("symlink", "file", "fifo"))
def test_resolution_rejects_incompatible_intermediate_components(
    tmp_path: Path, kind: str
) -> None:
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    component = trusted_root / "blocked"
    if kind == "symlink":
        outside = tmp_path / "outside"
        outside.mkdir()
        component.symlink_to(outside, target_is_directory=True)
    elif kind == "file":
        component.write_text("not a directory", encoding="utf-8")
    else:
        os.mkfifo(component)

    with pytest.raises(RepositoryTargetError, match="incompatible component"):
        resolve_repository_target(trusted_root, "blocked/repository")


def test_resolution_rejects_symlinked_final_component(tmp_path: Path) -> None:
    trusted_root = tmp_path / "trusted"
    outside = tmp_path / "outside"
    trusted_root.mkdir()
    outside.mkdir()
    (trusted_root / "repository").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RepositoryTargetError, match="incompatible component"):
        resolve_repository_target(trusted_root, "repository")


def test_resolution_rejects_incompatible_trusted_root(tmp_path: Path) -> None:
    real_root = tmp_path / "real"
    real_root.mkdir()
    symlink_root = tmp_path / "trusted"
    symlink_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(RepositoryTargetError, match="trusted repository root"):
        resolve_repository_target(symlink_root, "repository")


def test_explicit_resolver_normalizes_trusted_host_dot_path() -> None:
    target = resolve_explicit_repository_target(".")

    assert target.root == Path.cwd()
    assert target.exists is True


def test_initializer_revalidates_forged_public_target_before_mutation(
    tmp_path: Path,
) -> None:
    trusted_root = tmp_path / "trusted"
    outside = tmp_path / "outside"
    trusted_root.mkdir()
    outside.mkdir()
    legitimate = resolve_repository_target(trusted_root, "repository")
    forged = ResolvedRepositoryTarget(
        trusted_root=legitimate.trusted_root,
        relative_parts=("..", "outside", "escaped"),
        verified_root_identity=legitimate.verified_root_identity,
        existing_parts=(),
        existing_prefix_identities=(),
        missing_parts=("..", "outside", "escaped"),
    )

    with pytest.raises(RepositoryTargetError, match="resolved repository target is invalid"):
        initialize_repository_target(forged, EMPTY_CONFIG)

    assert tuple(trusted_root.iterdir()) == ()
    assert tuple(outside.iterdir()) == ()


def test_nested_initialization_is_idempotent_and_config_conflicts_do_not_mutate(
    tmp_path: Path,
) -> None:
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    target = resolve_repository_target(trusted_root, "nested/repository")

    first = initialize_repository_target(target, EMPTY_CONFIG)
    config_identity = first.config.stat().st_ino
    first_entries = tuple(
        sorted(path.relative_to(first.root) for path in first.root.rglob("*"))
    )

    second_target = resolve_repository_target(trusted_root, "nested/repository")
    second = initialize_repository_target(second_target, EMPTY_CONFIG)
    with pytest.raises(RepositoryTargetError, match="configuration is incompatible"):
        initialize_repository_target(second_target, _different_config())

    assert second == first
    assert first.config.read_bytes() == EMPTY_CONFIG.to_bytes()
    assert first.config.stat().st_ino == config_identity
    assert tuple(
        sorted(path.relative_to(first.root) for path in first.root.rglob("*"))
    ) == first_entries


def test_initialization_rejects_nonempty_target_without_removing_user_content(
    tmp_path: Path,
) -> None:
    trusted_root = tmp_path / "trusted"
    repository = trusted_root / "repository"
    repository.mkdir(parents=True)
    user_file = repository / "owned-by-user.txt"
    user_file.write_text("preserve", encoding="utf-8")
    target = resolve_repository_target(trusted_root, "repository")

    with pytest.raises(RepositoryTargetError, match="non-empty"):
        initialize_repository_target(target, EMPTY_CONFIG)

    assert user_file.read_text(encoding="utf-8") == "preserve"
    assert tuple(repository.iterdir()) == (user_file,)


def test_interrupted_known_empty_layout_recovers_but_unknown_paths_are_preserved(
    tmp_path: Path,
) -> None:
    trusted_root = tmp_path / "trusted"
    repository = trusted_root / "repository"
    repository.mkdir(parents=True)
    (repository / ".study-agent.lock").write_bytes(b"")
    for name in ("state", "blobs"):
        (repository / name).mkdir()
    target = resolve_repository_target(trusted_root, "repository")

    paths = initialize_repository_target(target, EMPTY_CONFIG)

    assert paths.config.read_bytes() == EMPTY_CONFIG.to_bytes()
    assert paths.exports.is_dir()

    incompatible = trusted_root / "incompatible"
    incompatible.mkdir()
    (incompatible / ".study-agent.lock").write_bytes(b"")
    unknown = incompatible / "unknown.txt"
    unknown.write_text("preserve", encoding="utf-8")
    with pytest.raises(RepositoryTargetError, match="unknown paths"):
        initialize_repository_target(
            resolve_repository_target(trusted_root, "incompatible"), EMPTY_CONFIG
        )
    assert unknown.read_text(encoding="utf-8") == "preserve"


def test_existing_config_recovers_hardlinked_temporary_publication(tmp_path: Path) -> None:
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    target = resolve_repository_target(trusted_root, "repository")
    paths = initialize_repository_target(target, EMPTY_CONFIG)
    temporary = paths.root / ".study-agent.json.tmp"
    os.link(paths.config, temporary)
    config_identity = paths.config.stat().st_ino

    recovered = initialize_repository_target(
        resolve_repository_target(trusted_root, "repository"), EMPTY_CONFIG
    )

    assert recovered.config.read_bytes() == EMPTY_CONFIG.to_bytes()
    assert recovered.config.stat().st_ino == config_identity
    assert not temporary.exists()


def test_concurrent_initializers_share_one_resolved_target_and_converge(
    tmp_path: Path,
) -> None:
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    target = resolve_repository_target(trusted_root, "nested/repository")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = tuple(
            pool.map(
                lambda _: initialize_repository_target(target, EMPTY_CONFIG), range(16)
            )
        )

    assert all(result == results[0] for result in results)
    assert results[0].config.read_bytes() == EMPTY_CONFIG.to_bytes()
    assert (results[0].root / ".study-agent.lock").is_file()


def test_replacement_before_first_mkdir_cannot_escape_or_leave_owned_tail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trusted_root = tmp_path / "trusted"
    displaced_root = tmp_path / "displaced-trusted"
    outside = tmp_path / "outside"
    trusted_root.mkdir()
    outside.mkdir()
    target = resolve_repository_target(trusted_root, "nested/repository")
    real_mkdir = os.mkdir
    replaced = False

    def mkdir_with_root_replacement(
        name: str | os.PathLike[str],
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> None:
        nonlocal replaced
        if name == "nested" and not replaced:
            replaced = True
            trusted_root.rename(displaced_root)
            trusted_root.symlink_to(outside, target_is_directory=True)
        real_mkdir(name, mode, dir_fd=dir_fd)

    monkeypatch.setattr(
        "study_agent.adapters.filesystem.repository_target.os.mkdir",
        mkdir_with_root_replacement,
    )

    with pytest.raises(RepositoryTargetError, match="identity changed"):
        initialize_repository_target(target, EMPTY_CONFIG)

    assert replaced is True
    assert tuple(outside.iterdir()) == ()
    assert tuple(displaced_root.iterdir()) == ()


@pytest.mark.parametrize("replace_after_link", (False, True))
def test_parent_replacement_around_publication_rolls_back_exact_owned_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replace_after_link: bool,
) -> None:
    trusted_root = tmp_path / "trusted"
    outside = tmp_path / "outside"
    displaced = trusted_root / "displaced"
    nested = trusted_root / "nested"
    trusted_root.mkdir()
    outside.mkdir()
    target = resolve_repository_target(trusted_root, "nested/repository")
    real_link = os.link
    replaced = False

    def replace_parent() -> None:
        nonlocal replaced
        nested.rename(displaced)
        nested.symlink_to(outside, target_is_directory=True)
        replaced = True

    def link_with_parent_replacement(
        source: str | os.PathLike[str],
        destination: str | os.PathLike[str],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        if not replace_after_link:
            replace_parent()
        real_link(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )
        if replace_after_link:
            replace_parent()

    monkeypatch.setattr(
        "study_agent.adapters.filesystem.repository_target.os.link",
        link_with_parent_replacement,
    )

    with pytest.raises(RepositoryTargetError, match="identity changed"):
        initialize_repository_target(target, EMPTY_CONFIG)

    assert replaced is True
    assert tuple(outside.iterdir()) == ()
    assert tuple(displaced.iterdir()) == ()


def test_rollback_preserves_config_inode_replaced_by_another_actor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    repository = trusted_root / "repository"
    target = resolve_repository_target(trusted_root, "repository")
    real_link = os.link
    raced_payload = b"owned by another actor\n"

    def link_then_replace_config(
        source: str | os.PathLike[str],
        destination: str | os.PathLike[str],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        real_link(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )
        config_path = repository / CONFIG_FILENAME
        config_path.unlink()
        config_path.write_bytes(raced_payload)

    monkeypatch.setattr(
        "study_agent.adapters.filesystem.repository_target.os.link",
        link_then_replace_config,
    )

    with pytest.raises(RepositoryTargetError, match="configuration is incompatible"):
        initialize_repository_target(target, EMPTY_CONFIG)

    assert (repository / CONFIG_FILENAME).read_bytes() == raced_payload


def test_binding_failure_rollback_preserves_replaced_lock_inode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trusted_root = tmp_path / "trusted"
    outside = tmp_path / "outside"
    displaced = trusted_root / "displaced"
    nested = trusted_root / "nested"
    repository_after_displacement = displaced / "repository"
    trusted_root.mkdir()
    outside.mkdir()
    target = resolve_repository_target(trusted_root, "nested/repository")
    real_link = os.link
    replacement_payload = b"replacement lock\n"

    def link_then_replace_lock_and_parent(
        source: str | os.PathLike[str],
        destination: str | os.PathLike[str],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        real_link(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )
        lock = nested / "repository" / ".study-agent.lock"
        lock.unlink()
        lock.write_bytes(replacement_payload)
        nested.rename(displaced)
        nested.symlink_to(outside, target_is_directory=True)

    monkeypatch.setattr(
        "study_agent.adapters.filesystem.repository_target.os.link",
        link_then_replace_lock_and_parent,
    )

    with pytest.raises(RepositoryTargetError, match="identity changed"):
        initialize_repository_target(target, EMPTY_CONFIG)

    replacement_lock = repository_after_displacement / ".study-agent.lock"
    assert replacement_lock.read_bytes() == replacement_payload
    assert not (repository_after_displacement / CONFIG_FILENAME).exists()
    assert tuple(outside.iterdir()) == ()


def test_config_read_rejects_mode_change_during_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    target = resolve_repository_target(trusted_root, "repository")
    paths = initialize_repository_target(target, EMPTY_CONFIG)
    real_read = os.read
    changed = False

    def read_then_change_mode(descriptor: int, length: int) -> bytes:
        nonlocal changed
        payload = real_read(descriptor, length)
        if payload and not changed:
            changed = True
            paths.config.chmod(0o640)
        return payload

    monkeypatch.setattr(
        "study_agent.adapters.filesystem.repository_target.os.read",
        read_then_change_mode,
    )

    with pytest.raises(RepositoryTargetError, match="configuration is incompatible"):
        initialize_repository_target(
            resolve_repository_target(trusted_root, "repository"), EMPTY_CONFIG
        )

    assert changed is True


def test_initialization_uses_nofollow_fd_relative_mutation_and_link_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    target = resolve_repository_target(trusted_root, "nested/repository")
    mkdir_calls: list[tuple[str | os.PathLike[str], int | None]] = []
    link_calls: list[tuple[object, object, int | None, int | None, bool]] = []
    real_mkdir = os.mkdir
    real_link = os.link

    def observed_mkdir(
        name: str | os.PathLike[str],
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> None:
        mkdir_calls.append((name, dir_fd))
        real_mkdir(name, mode, dir_fd=dir_fd)

    def observed_link(
        source: str | os.PathLike[str],
        destination: str | os.PathLike[str],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        link_calls.append(
            (source, destination, src_dir_fd, dst_dir_fd, follow_symlinks)
        )
        real_link(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )

    def forbidden_replace(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            f"os.replace must not publish repository config: {args!r} {kwargs!r}"
        )

    monkeypatch.setattr(
        "study_agent.adapters.filesystem.repository_target.os.mkdir", observed_mkdir
    )
    monkeypatch.setattr(
        "study_agent.adapters.filesystem.repository_target.os.link", observed_link
    )
    monkeypatch.setattr(
        "study_agent.adapters.filesystem.repository_target.os.replace",
        forbidden_replace,
    )

    initialize_repository_target(target, EMPTY_CONFIG)

    assert [name for name, _ in mkdir_calls] == [
        "nested",
        "repository",
        "state",
        "blobs",
        "exports",
    ]
    assert all(dir_fd is not None for _, dir_fd in mkdir_calls)
    assert link_calls == [
        (
            ".study-agent.json.tmp",
            CONFIG_FILENAME,
            link_calls[0][2],
            link_calls[0][2],
            False,
        )
    ]


def test_existing_components_are_opened_directory_nofollow_relative_to_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trusted_root = tmp_path / "trusted"
    existing = trusted_root / "existing"
    existing.mkdir(parents=True)
    real_open = os.open
    component_calls: list[tuple[int, int | None]] = []

    def observed_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if path == "existing":
            component_calls.append((flags, dir_fd))
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(
        "study_agent.adapters.filesystem.repository_target.os.open", observed_open
    )

    resolve_repository_target(trusted_root, "existing/repository")

    assert len(component_calls) == 1
    flags, parent_fd = component_calls[0]
    assert parent_fd is not None
    assert flags & os.O_NOFOLLOW
    assert flags & os.O_DIRECTORY
