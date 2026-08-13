from __future__ import annotations

import asyncio
import base64
import builtins
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import os
import shutil
import sys
import sysconfig
from collections.abc import Coroutine, Sequence
from hashlib import sha256
from importlib.machinery import ModuleSpec
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from types import ModuleType
from typing import Any, cast

import pytest

import study_agent.adapters.host.openai_responses as responses_adapter
import study_agent.adapters.package_trust as package_trust
from study_agent.adapters.host.openai_responses import (
    OpenAIResponsesConfigurationError,
    OpenAIResponsesTutorConfig,
    OpenAIResponsesTutorDecisionPort,
)
from study_agent.adapters.package_trust import (
    PackageTrustBinding,
    PackageTrustError,
    deserialize_identity,
    discard_verified_package,
    identity_matches,
    load_verified_package,
    serialize_identity,
    use_verified_package,
    validate_distribution,
)
from study_agent.adapters.workarounds import worker
from study_agent.hosts import AdvertisedCapability, TutorHostContext


def _manifest(root: Path, package_name: str, files: tuple[str, ...]) -> PackageTrustBinding:
    return PackageTrustBinding.from_manifest(
        package_name,
        root,
        "1.0.0",
        {
            relative: sha256((root / relative).read_bytes()).hexdigest()
            for relative in files
        },
    )


def _package(tmp_path: Path, source: str = "VALUE = 1\n") -> tuple[Path, PackageTrustBinding]:
    root = tmp_path / "site-packages"
    package = root / "securepkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(source, encoding="utf-8")
    return root, _manifest(root, "securepkg", ("securepkg/__init__.py",))


def test_identity_wire_is_canonical_and_non_executable(tmp_path: Path) -> None:
    _root, binding = _package(tmp_path)
    identity = validate_distribution(binding)

    encoded = serialize_identity(identity)
    assert deserialize_identity(encoded) == identity
    with pytest.raises(PackageTrustError, match="canonical"):
        deserialize_identity(b" " + encoded)
    assert b"pickle" not in encoded


def test_first_load_rejects_byte_identical_root_replacement(tmp_path: Path) -> None:
    root, binding = _package(tmp_path)
    identity = validate_distribution(binding)
    replacement = tmp_path / "replacement"
    shutil.copytree(root, replacement)
    old = tmp_path / "old-site-packages"
    root.rename(old)
    replacement.rename(root)

    assert not identity_matches(identity)
    with pytest.raises(PackageTrustError, match="changed"):
        load_verified_package(identity)


def test_hardlinked_executable_resource_is_rejected(tmp_path: Path) -> None:
    root, binding = _package(tmp_path)
    alias = tmp_path / "alias.py"
    os.link(root / "securepkg" / "__init__.py", alias)

    with pytest.raises(PackageTrustError, match=r"identity|unavailable"):
        validate_distribution(binding)


def test_distribution_validation_does_not_call_mutable_metadata_hooks(
    tmp_path: Path,
) -> None:
    _root, binding = _package(tmp_path)

    class Exploding:
        def __getattr__(self, _name: str) -> object:
            raise AssertionError("mutable distribution hook was called")

    assert validate_distribution(binding, Exploding(), Exploding()).binding == binding


def _wheel_binding(
    tmp_path: Path,
    *,
    record_rows: list[str],
    entry_points: str | None = None,
) -> PackageTrustBinding:
    root = tmp_path / "venv" / "lib" / "python3.13" / "site-packages"
    package = root / "securepkg"
    metadata_root = root / "securepkg-1.0.0.dist-info"
    package.mkdir(parents=True)
    metadata_root.mkdir()
    (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (metadata_root / "METADATA").write_text(
        "Metadata-Version: 2.3\nName: securepkg\nVersion: 1.0.0\n",
        encoding="utf-8",
    )
    if entry_points is not None:
        (metadata_root / "entry_points.txt").write_text(entry_points, encoding="utf-8")
    (metadata_root / "RECORD").write_text("\n".join(record_rows) + "\n", encoding="utf-8")
    files = tuple(
        row.split(",", 1)[0]
        for row in record_rows
        if not row.startswith("..")
    )
    return _manifest(tmp_path / "venv" / "lib" / "python3.13" / "site-packages", "securepkg", files)


def test_duplicate_record_entries_are_bounded_and_rejected(tmp_path: Path) -> None:
    binding = _wheel_binding(
        tmp_path,
        record_rows=[
            "securepkg/__init__.py,,",
            "securepkg/__init__.py,,",
            "securepkg-1.0.0.dist-info/METADATA,,",
            "securepkg-1.0.0.dist-info/RECORD,,",
        ],
    )

    with pytest.raises(PackageTrustError, match="RECORD"):
        validate_distribution(binding)


def test_launcher_allowlist_requires_declared_executable_entry_point(tmp_path: Path) -> None:
    venv = tmp_path / "venv"
    launcher = venv / "bin" / "securepkg"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    launcher.chmod(0o755)
    binding = _wheel_binding(
        tmp_path,
        record_rows=[
            "securepkg/__init__.py,,",
            "securepkg-1.0.0.dist-info/METADATA,,",
            "securepkg-1.0.0.dist-info/RECORD,,",
            "securepkg-1.0.0.dist-info/entry_points.txt,,",
            "../../../bin/securepkg,,",
        ],
        entry_points="[console_scripts]\nsecurepkg = securepkg:main\n",
    )

    assert validate_distribution(binding).binding == binding


def test_verified_reuse_reexecutes_after_module_export_mutation(tmp_path: Path) -> None:
    _root, binding = _package(tmp_path)
    identity = validate_distribution(binding)
    first = load_verified_package(identity)
    first.VALUE = 99  # type: ignore[attr-defined]
    second = load_verified_package(identity)

    assert second is not first
    assert second.VALUE == 1
    discard_verified_package("securepkg")


def test_worker_protocol_rejects_pickle_shaped_and_oversized_stdout() -> None:
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"cos\nsystem\n")
        os.close(write_fd)
        with pytest.raises(worker._WorkerProtocolError):
            worker._read_response(read_fd, monotonic() + 0.1)
    finally:
        os.close(read_fd)

    read_fd, write_fd = os.pipe()
    try:
        header = worker._RESPONSE_HEADER.pack(
            worker._PROTOCOL_MAGIC,
            worker._PROTOCOL_VERSION,
            0,
            worker.MAX_WORKER_INPUT_BYTES,
        )
        os.write(write_fd, header)
        os.close(write_fd)
        with pytest.raises(worker._WorkerProtocolError):
            worker._read_response(read_fd, monotonic() + 0.1)
    finally:
        os.close(read_fd)


def test_worker_source_contains_no_pickle_or_unbounded_communicate() -> None:
    source = Path(worker.__file__).read_text(encoding="utf-8")
    assert "pickle" not in source
    assert "communicate(" not in source
    assert "setsid=True" in source


def test_unbound_transitive_dependency_and_finder_are_rejected(tmp_path: Path) -> None:
    root = tmp_path.resolve() / "site-packages"
    package = root / "securepkg"
    package.mkdir(parents=True)
    marker = tmp_path / "executed"
    (package / "__init__.py").write_text(
        f"import hostile_dependency\nPath = {marker!r}\n", encoding="utf-8"
    )
    (root / "hostile_dependency.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    binding = _manifest(root, "securepkg", ("securepkg/__init__.py",))

    with pytest.raises(PackageTrustError, match="unbound dependency"):
        load_verified_package(validate_distribution(binding))
    assert not marker.exists()


def test_declared_transitive_dependency_is_verified_and_import_hook_is_untouched(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve() / "site-packages"
    package = root / "securepkg"
    dependency = root / "declared_dependency"
    package.mkdir(parents=True)
    dependency.mkdir()
    (dependency / "__init__.py").write_text("VALUE = 41\n", encoding="utf-8")
    (package / "__init__.py").write_text(
        "from declared_dependency import VALUE\nVALUE += 1\n", encoding="utf-8"
    )
    files = ("declared_dependency/__init__.py", "securepkg/__init__.py")
    binding = _manifest(root, "securepkg", files)
    original_import = builtins.__import__

    loaded = load_verified_package(validate_distribution(binding))
    assert loaded.VALUE == 42
    assert builtins.__import__ is original_import
    discard_verified_package("securepkg")


def test_private_graph_supports_two_wheels_and_never_exposes_authority(
    tmp_path: Path,
) -> None:
    root = tmp_path / "site-packages"
    package = root / "securepkg"
    dependency = root / "declared_dependency"
    primary_dist = root / "securepkg-1.0.0.dist-info"
    dependency_dist = root / "declared_dependency-2.0.0.dist-info"
    package.mkdir(parents=True)
    dependency.mkdir()
    primary_dist.mkdir()
    dependency_dist.mkdir()
    (dependency / "__init__.py").write_text("VALUE = 41\n", encoding="utf-8")
    (package / "__init__.py").write_text(
        "from declared_dependency import VALUE\nVALUE += 1\n", encoding="utf-8"
    )
    (primary_dist / "METADATA").write_text(
        "Metadata-Version: 2.3\nName: securepkg\nVersion: 1.0.0\n",
        encoding="utf-8",
    )
    (dependency_dist / "METADATA").write_text(
        "Metadata-Version: 2.3\nName: declared_dependency\nVersion: 2.0.0\n",
        encoding="utf-8",
    )
    primary_rows = [
        "securepkg/__init__.py,,",
        "securepkg-1.0.0.dist-info/METADATA,,",
        "securepkg-1.0.0.dist-info/RECORD,,",
    ]
    dependency_rows = [
        "declared_dependency/__init__.py,,",
        "declared_dependency-2.0.0.dist-info/METADATA,,",
        "declared_dependency-2.0.0.dist-info/RECORD,,",
    ]
    (primary_dist / "RECORD").write_text("\n".join(primary_rows) + "\n", encoding="utf-8")
    (dependency_dist / "RECORD").write_text(
        "\n".join(dependency_rows) + "\n", encoding="utf-8"
    )
    files = tuple(
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )
    binding = _manifest(root, "securepkg", files)

    loaded = load_verified_package(validate_distribution(binding))
    try:
        assert loaded.VALUE == 42
        assert "securepkg" not in sys.modules
        assert "declared_dependency" not in sys.modules
        assert all(
            not name.startswith(("securepkg.", "declared_dependency."))
            for name in sys.modules
        )
    finally:
        discard_verified_package("securepkg")


@pytest.mark.parametrize(
    ("primary_rows", "primary_version", "secondary_rows"),
    (
        (
            [
                "securepkg-1.0.0.dist-info/METADATA,,",
                "securepkg-1.0.0.dist-info/RECORD,,",
            ],
            "1.0.0",
            [
                "declared_dependency/__init__.py,,",
                "declared_dependency-2.0.0.dist-info/METADATA,,",
                "declared_dependency-2.0.0.dist-info/RECORD,,",
            ],
        ),
        (
            [
                "securepkg/__init__.py,,",
                "securepkg-1.0.0.dist-info/METADATA,,",
                "securepkg-1.0.0.dist-info/RECORD,,",
            ],
            "9.9.9",
            [
                "declared_dependency/__init__.py,,",
                "declared_dependency-2.0.0.dist-info/METADATA,,",
                "declared_dependency-2.0.0.dist-info/RECORD,,",
            ],
        ),
        (
            [
                "securepkg/__init__.py,,",
                "securepkg-1.0.0.dist-info/METADATA,,",
                "securepkg-1.0.0.dist-info/RECORD,,",
            ],
            "1.0.0",
            [
                "securepkg/__init__.py,,",
                "declared_dependency/__init__.py,,",
                "declared_dependency-2.0.0.dist-info/METADATA,,",
                "declared_dependency-2.0.0.dist-info/RECORD,,",
            ],
        ),
    ),
)
def test_wheel_partition_rejects_missing_overlap_and_metadata_mismatch(
    tmp_path: Path,
    primary_rows: list[str],
    primary_version: str,
    secondary_rows: list[str],
) -> None:
    root = tmp_path / "site-packages"
    for relative in (
        "securepkg/__init__.py",
        "declared_dependency/__init__.py",
        "securepkg-1.0.0.dist-info/METADATA",
        "securepkg-1.0.0.dist-info/RECORD",
        "declared_dependency-2.0.0.dist-info/METADATA",
        "declared_dependency-2.0.0.dist-info/RECORD",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
    (root / "securepkg/__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "declared_dependency/__init__.py").write_text(
        "VALUE = 2\n", encoding="utf-8"
    )
    (root / "securepkg-1.0.0.dist-info/METADATA").write_text(
        f"Metadata-Version: 2.3\nName: securepkg\nVersion: {primary_version}\n",
        encoding="utf-8",
    )
    (root / "declared_dependency-2.0.0.dist-info/METADATA").write_text(
        "Metadata-Version: 2.3\nName: declared_dependency\nVersion: 2.0.0\n",
        encoding="utf-8",
    )
    (root / "securepkg-1.0.0.dist-info/RECORD").write_text(
        "\n".join(primary_rows) + "\n", encoding="utf-8"
    )
    (root / "declared_dependency-2.0.0.dist-info/RECORD").write_text(
        "\n".join(secondary_rows) + "\n", encoding="utf-8"
    )
    files = tuple(
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )
    binding = _manifest(root, "securepkg", files)

    with pytest.raises(PackageTrustError, match="RECORD"):
        validate_distribution(binding)


def test_private_importlib_lazy_load_cleans_up_after_transaction(
    tmp_path: Path,
) -> None:
    root = tmp_path / "site-packages"
    package = root / "securepkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "import importlib\n"
        "VALUE = importlib.import_module('securepkg.helper').VALUE\n",
        encoding="utf-8",
    )
    (package / "helper.py").write_text("VALUE = 7\n", encoding="utf-8")
    binding = _manifest(
        root,
        "securepkg",
        ("securepkg/__init__.py", "securepkg/helper.py"),
    )
    identity = validate_distribution(binding)

    loaded = load_verified_package(identity)
    assert loaded.VALUE == 7
    discard_verified_package("securepkg")
    assert "securepkg" not in sys.modules
    assert "securepkg.helper" not in sys.modules


def test_importlib_compat_module_is_inert_and_mutation_cannot_change_authority(
    tmp_path: Path,
) -> None:
    root, binding = _package(tmp_path)
    package = root / "securepkg"
    (package / "helper.py").write_text("VALUE = 7\n", encoding="utf-8")
    binding = _manifest(
        root,
        "securepkg",
        ("securepkg/__init__.py", "securepkg/helper.py"),
    )
    identity = validate_distribution(binding)

    def mutate_compatibility_module(module: ModuleType) -> object:
        helper = importlib.import_module("securepkg.helper")
        helper.VALUE = 99  # type: ignore[attr-defined]
        return module.VALUE

    assert use_verified_package(identity, mutate_compatibility_module) == 1
    assert "securepkg.helper" not in sys.modules


def test_private_importlib_ignores_dynamic_forged_stdlib_preload(
    tmp_path: Path,
) -> None:
    root = tmp_path / "site-packages"
    package = root / "securepkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "import importlib\n"
        "import sys\n"
        "sys.modules['json'] = object()\n"
        "VALUE = importlib.import_module('json').JSONDecodeError.__name__\n",
        encoding="utf-8",
    )
    binding = _manifest(root, "securepkg", ("securepkg/__init__.py",))
    identity = validate_distribution(binding)
    missing = object()
    original_json = sys.modules.get("json", missing)
    try:
        loaded = load_verified_package(identity)
        assert loaded.VALUE == "JSONDecodeError"
    finally:
        discard_verified_package("securepkg")
        if original_json is missing:
            sys.modules.pop("json", None)
        else:
            sys.modules["json"] = cast(ModuleType, original_json)


def test_awaited_optional_helper_stays_private_through_close(tmp_path: Path) -> None:
    root = tmp_path / "site-packages"
    package = root / "securepkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "class Responses:\n"
        "    async def create(self):\n"
        "        return 'ok'\n"
        "class AsyncOpenAI:\n"
        "    def __init__(self, **kwargs):\n"
        "        self.responses = Responses()\n"
        "        self.closed = False\n"
        "    async def close(self):\n"
        "        self.closed = True\n",
        encoding="utf-8",
    )
    binding = _manifest(root, "securepkg", ("securepkg/__init__.py",))
    identity = validate_distribution(binding)

    async def execute(module: ModuleType) -> str:
        client = cast(Any, module).AsyncOpenAI(api_key="redacted")
        try:
            return cast(str, await client.responses.create())
        finally:
            await client.close()

    pending = cast(Coroutine[Any, Any, str], use_verified_package(identity, execute))
    assert asyncio.run(pending) == "ok"
    assert "securepkg" not in sys.modules


def test_overlapping_awaited_transactions_are_serialized_and_cleaned(
    tmp_path: Path,
) -> None:
    _root, binding = _package(tmp_path)
    identity = validate_distribution(binding)

    async def execute(module: ModuleType) -> int:
        await asyncio.sleep(0)
        return cast(int, module.VALUE)

    async def run() -> None:
        pending = cast(Coroutine[Any, Any, int], use_verified_package(identity, execute))
        task: asyncio.Task[int] = asyncio.create_task(pending)
        await asyncio.sleep(0)
        with pytest.raises(PackageTrustError, match="busy"):
            use_verified_package(identity, lambda _module: 2)
        assert await task == 1
        assert use_verified_package(identity, lambda module: module.VALUE) == 1

    asyncio.run(run())
    assert "securepkg" not in sys.modules


def test_abandoned_async_operation_retains_no_transaction(tmp_path: Path) -> None:
    _root, binding = _package(tmp_path)
    identity = validate_distribution(binding)

    async def execute(module: ModuleType) -> int:
        await asyncio.sleep(0)
        return cast(int, module.VALUE)

    pending = cast(Coroutine[Any, Any, int], use_verified_package(identity, execute))
    pending.close()
    assert use_verified_package(identity, lambda module: module.VALUE) == 1


def test_same_loop_peer_import_is_not_intercepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, binding = _package(tmp_path)
    peer_root = tmp_path / "peer-site"
    peer_root.mkdir()
    (peer_root / "peer_dependency.py").write_text("VALUE = 7\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(peer_root))
    identity = validate_distribution(binding)

    async def execute(module: ModuleType) -> int:
        async def peer() -> int:
            imported = __import__("peer_dependency")
            return cast(int, imported.VALUE)

        peer_value = await asyncio.create_task(peer())
        return cast(int, module.VALUE) + peer_value

    assert asyncio.run(cast(Coroutine[Any, Any, int], use_verified_package(identity, execute))) == 8


def test_native_load_does_not_reopen_swapped_package_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = (tmp_path / "site-packages").resolve()
    package = root / "jiter"
    dist = root / "jiter-0.16.0.dist-info"
    package.mkdir(parents=True)
    dist.mkdir()
    suffix = importlib.machinery.EXTENSION_SUFFIXES[0]
    native_relative = f"jiter/jiter{suffix}"
    (package / "__init__.py").write_text(
        "from .jiter import VALUE\n", encoding="utf-8"
    )
    native_path = root / native_relative
    native_path.write_bytes(b"approved-native")
    platform_tag = sysconfig.get_platform().replace("-", "_").replace(".", "_")
    interpreter = f"cp{sys.version_info.major}{sys.version_info.minor}"
    abi = "abi3" if ".abi3" in suffix else interpreter
    (dist / "METADATA").write_text(
        "Metadata-Version: 2.3\nName: jiter\nVersion: 0.16.0\n",
        encoding="utf-8",
    )
    (dist / "WHEEL").write_text(
        f"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: {interpreter}-{abi}-{platform_tag}\n",
        encoding="utf-8",
    )
    def record_line(relative: str) -> str:
        path = root / relative
        digest = base64.urlsafe_b64encode(sha256(path.read_bytes()).digest())
        return f"{relative},sha256={digest.decode('ascii').rstrip('=')},{path.stat().st_size}"

    record_rows = [
        record_line(native_relative),
        record_line("jiter/__init__.py"),
        record_line("jiter-0.16.0.dist-info/METADATA"),
        record_line("jiter-0.16.0.dist-info/WHEEL"),
        "jiter-0.16.0.dist-info/RECORD,,",
    ]
    (dist / "RECORD").write_text("\n".join(record_rows) + "\n", encoding="utf-8")
    files = tuple(
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )
    binding = PackageTrustBinding.from_manifest(
        "jiter",
        root,
        "0.16.0",
        {relative: sha256((root / relative).read_bytes()).hexdigest() for relative in files},
    )
    identity = validate_distribution(binding)
    marker = tmp_path / "native-executed"
    original_read = package_trust.read_verified_bytes

    def swap_after_read(current: Any, relative: str) -> bytes:
        value = original_read(current, relative)
        if relative == native_relative:
            native_path.write_bytes(b"malicious-native")
        return value

    class FakeNativeLoader:
        def __init__(self, fullname: str, path: str) -> None:
            self.fullname = fullname
            self.path = path

        def create_module(self, _spec: object) -> ModuleType:
            return ModuleType(self.fullname)

        def exec_module(self, module: ModuleType) -> None:
            marker.write_text(
                "malicious" if self.path == str(native_path) else "sealed",
                encoding="utf-8",
            )
            module.VALUE = 1  # type: ignore[attr-defined]

    monkeypatch.setattr(package_trust, "read_verified_bytes", swap_after_read)
    monkeypatch.setattr(
        importlib.machinery,
        "ExtensionFileLoader",
        FakeNativeLoader,
    )
    with pytest.raises(PackageTrustError, match="changed"):
        load_verified_package(identity)
    assert marker.read_text(encoding="utf-8") == "sealed"


def test_cancelled_awaited_transaction_cleans_exact_token(tmp_path: Path) -> None:
    _root, binding = _package(tmp_path)
    identity = validate_distribution(binding)

    async def execute(module: ModuleType) -> int:
        await asyncio.sleep(10)
        return cast(int, module.VALUE)

    async def run() -> None:
        pending = cast(Coroutine[Any, Any, object], use_verified_package(identity, execute))
        task = asyncio.create_task(pending)
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert use_verified_package(identity, lambda module: module.VALUE) == 1

    asyncio.run(run())
    assert "securepkg" not in sys.modules


def test_openai_request_and_close_stay_inside_verified_transaction(tmp_path: Path) -> None:
    root = tmp_path / "site-packages"
    package = root / "openai"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "class Responses:\n"
        "    async def create(self, **kwargs):\n"
        "        return {'status': 'completed', 'error': None,\n"
        "                'incomplete_details': None, 'output': [\n"
        "                    {'type': 'message', 'role': 'assistant',\n"
        "                     'content': [{'type': 'output_text',\n"
        "                                  'text': '"
        "{\\\"decision\\\":{\\\"kind\\\":\\\"assistant_message\\\","
        "\\\"message\\\":\\\"ok\\\"}}'}]}]}\n"
        "class AsyncOpenAI:\n"
        "    def __init__(self, **kwargs):\n"
        "        self.responses = Responses()\n"
        "    async def close(self):\n"
        "        return None\n",
        encoding="utf-8",
    )
    binding = PackageTrustBinding.from_manifest(
        "openai",
        root,
        "2.46.0",
        {
            "openai/__init__.py": sha256(
                (package / "__init__.py").read_bytes()
            ).hexdigest()
        },
    )

    class Interruption:
        def is_interrupted(self) -> bool:
            return False

    context = TutorHostContext(
        course_id="course",
        session_id="session",
        tutor_snapshot_sequence=1,
        learner_evidence_through_sequence=1,
        tutor_snapshot={"status": "active"},
        learner_evidence={"estimates": ()},
        advertised_capabilities=(
            AdvertisedCapability(
                "grounding.ask",
                "grounding.ask@1.0.0",
                "a" * 64,
                {
                    "type": "object",
                    "properties": {"topic": {"type": "string", "minLength": 1}},
                    "required": ("topic",),
                    "additionalProperties": False,
                },
                True,
            ),
        ),
    )
    port = OpenAIResponsesTutorDecisionPort(
        OpenAIResponsesTutorConfig("gpt-5.6", "OPENAI_API_KEY"),
        package_trust=binding,
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        decision = asyncio.run(port.decide(context, Interruption()))

    assert decision.message == "ok"  # type: ignore[union-attr]
    assert "openai" not in sys.modules


def test_spawned_verified_thread_cannot_import_unbound_dependency(tmp_path: Path) -> None:
    root = tmp_path / "site-packages"
    package = root / "securepkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "from threading import Thread\n"
        "errors = []\n"
        "def run():\n"
        "    try:\n"
        "        import hostile_dependency\n"
        "    except Exception as error:\n"
        "        errors.append(type(error).__name__)\n"
        "thread = Thread(target=run)\n"
        "thread.start()\n"
        "thread.join()\n"
        "VALUE = errors[0] if errors else 'missing'\n",
        encoding="utf-8",
    )
    (root / "hostile_dependency.py").write_text("VALUE = 99\n", encoding="utf-8")
    binding = _manifest(root, "securepkg", ("securepkg/__init__.py",))

    loaded = load_verified_package(validate_distribution(binding))
    try:
        assert loaded.VALUE == "PackageTrustError"
    finally:
        discard_verified_package("securepkg")


def test_verified_use_isolated_from_sys_modules_export_race(tmp_path: Path) -> None:
    _root, binding = _package(tmp_path)
    identity = validate_distribution(binding)
    load_verified_package(identity)
    started = Event()

    def mutate_export() -> None:
        started.wait(timeout=1)
        module = sys.modules.get("securepkg")
        if module is not None:
            module.VALUE = 99  # type: ignore[attr-defined]

    thread = Thread(target=mutate_export)
    thread.start()
    try:
        def read_export(module: ModuleType) -> object:
            started.set()
            thread.join(timeout=1)
            return module.VALUE

        assert use_verified_package(identity, read_export) == 1
    finally:
        thread.join(timeout=1)
        discard_verified_package("securepkg")


def test_peer_thread_stdlib_import_is_not_intercepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, binding = _package(tmp_path)
    identity = validate_distribution(binding)
    monkeypatch.delitem(sys.modules, "fractions", raising=False)
    monkeypatch.delitem(sys.modules, "_decimal", raising=False)
    entered = Event()
    completed = Event()
    errors: list[BaseException] = []

    def import_fraction() -> None:
        entered.wait(timeout=1)
        try:
            fractions = __import__("fractions")
            fractions.Fraction(1, 2)
        except BaseException as error:
            errors.append(error)
        finally:
            completed.set()

    thread = Thread(target=import_fraction)
    thread.start()
    try:
        def block_verified_use(module: ModuleType) -> object:
            entered.set()
            assert completed.wait(timeout=1)
            return module.VALUE

        assert use_verified_package(identity, block_verified_use) == 1
        assert errors == []
    finally:
        thread.join(timeout=1)
        discard_verified_package("securepkg")


def test_fake_stdlib_preload_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _root, binding = _package(tmp_path, "import json\nVALUE = 1\n")
    monkeypatch.setitem(sys.modules, "json", ModuleType("json"))

    with pytest.raises(PackageTrustError, match="stdlib"):
        load_verified_package(validate_distribution(binding))


def test_fake_stdlib_finder_is_bypassed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _root, binding = _package(tmp_path, "import json\nVALUE = json.JSONDecodeError.__name__\n")

    class FakeLoader(importlib.abc.Loader):
        def create_module(self, _spec: object) -> ModuleType:
            return ModuleType("json")

        def exec_module(self, _module: ModuleType) -> None:
            raise AssertionError("fake stdlib loader executed")

    class FakeFinder(importlib.abc.MetaPathFinder):
        def find_spec(
            self,
            fullname: str,
            _path: Sequence[str] | None = None,
            _target: ModuleType | None = None,
        ) -> ModuleSpec | None:
            if fullname == "json":
                return importlib.util.spec_from_loader(fullname, FakeLoader())
            return None

    monkeypatch.delitem(sys.modules, "json", raising=False)
    monkeypatch.setattr(sys, "meta_path", [FakeFinder(), *sys.meta_path])

    loaded = load_verified_package(validate_distribution(binding))
    assert loaded.VALUE == "JSONDecodeError"
    discard_verified_package("securepkg")


def test_same_stat_bootstrap_replacement_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "worker.py"
    path.write_text("A", encoding="utf-8")
    expected = worker._capture_file_digest(path)
    assert expected is not None
    metadata = path.stat()
    path.write_text("B", encoding="utf-8")
    os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))

    with pytest.raises(worker.PdfWorkerError, match="changed"):
        worker._read_file_digest(path, expected)


def test_readiness_rejects_empty_and_control_character_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        responses_adapter,
        "_verified_openai_factory",
        lambda: pytest.fail("invalid readiness key must not construct a client"),
    )
    port = OpenAIResponsesTutorDecisionPort(
        OpenAIResponsesTutorConfig("gpt-5.6", "OPENAI_API_KEY")
    )
    for value in ("", "bad\nkey"):
        monkeypatch.setenv("OPENAI_API_KEY", value)
        with pytest.raises(OpenAIResponsesConfigurationError, match="unavailable"):
            port._build_default_client()
