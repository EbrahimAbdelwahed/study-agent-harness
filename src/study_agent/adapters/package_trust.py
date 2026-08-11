"""Host-owned trust transactions for optional Python packages.

Optional packages are executable input.  This module keeps the trust decision
separate from importlib metadata, interpreter search paths, and package-owned
claims.  A host supplies an absolute root and an immutable manifest of expected
files and digests; the loader executes source bytes read from verified file
descriptors and never reuses a mutable module as trust evidence.
"""

from __future__ import annotations

import asyncio
import base64
import builtins
import csv
import importlib.abc
import importlib.machinery
import importlib.util
import inspect
import json
import os
import re
import stat
import sys
import sysconfig
import tempfile
from collections.abc import Callable, Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from threading import RLock, get_ident
from types import ModuleType
from typing import Final

IDENTITY_READ_SIZE: Final = 64 * 1024
MAX_IDENTITY_FILE_BYTES: Final = 64 * 1024 * 1024
MAX_PACKAGE_FILE_COUNT: Final = 4096
MAX_PACKAGE_AGGREGATE_BYTES: Final = 256 * 1024 * 1024
MAX_SERIALIZED_IDENTITY_BYTES: Final = 2 * 1024 * 1024
MAX_METADATA_BYTES: Final = 256 * 1024
MAX_RECORD_BYTES: Final = 8 * 1024 * 1024
MAX_METADATA_LINE_BYTES: Final = 4096
MAX_RECORD_LINE_BYTES: Final = 8192
MAX_RECORD_ENTRIES: Final = MAX_PACKAGE_FILE_COUNT
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PACKAGE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_VERSION = re.compile(r"^[^\x00\r\n]{1,256}$")
_LAUNCHER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_IDENTITY_SCHEMA = 1


def _current_task() -> object | None:
    """Return the current asyncio task without requiring a running loop."""

    try:
        return asyncio.current_task()
    except RuntimeError:
        return None


class PackageTrustError(RuntimeError):
    """The host binding or immutable package transaction is invalid."""


@dataclass(frozen=True, slots=True)
class _NativePackagePolicy:
    package_name: str
    expected_version: str
    member: str


_NATIVE_PACKAGE_POLICIES: Final[tuple[_NativePackagePolicy, ...]] = (
    _NativePackagePolicy("jiter", "0.16.0", "jiter/jiter"),
    _NativePackagePolicy(
        "pydantic_core", "2.46.4", "pydantic_core/_pydantic_core"
    ),
)


@dataclass(frozen=True, slots=True)
class ExpectedPackageFile:
    """One host-supplied, root-relative file digest."""

    relative_path: str
    digest: str
    size: int | None = None

    def __post_init__(self) -> None:
        relative = _relative_path(self.relative_path)
        if not _SHA256.fullmatch(self.digest):
            raise ValueError("package file digest must be a lowercase SHA-256 digest")
        if self.size is not None and (
            type(self.size) is not int
            or self.size < 0
            or self.size > MAX_IDENTITY_FILE_BYTES
        ):
            raise ValueError("package file size is invalid or oversized")
        object.__setattr__(self, "relative_path", relative)


@dataclass(frozen=True, slots=True)
class PackageTrustBinding:
    """An explicit host-owned package root, version, and bounded manifest."""

    package_name: str
    approved_root: Path
    expected_version: str
    manifest: tuple[ExpectedPackageFile, ...]

    def __post_init__(self) -> None:
        if not _PACKAGE.fullmatch(self.package_name):
            raise ValueError("package name must be one simple import namespace")
        if not isinstance(self.approved_root, Path) or not self.approved_root.is_absolute():
            raise ValueError("approved package root must be an absolute path")
        if (
            not isinstance(self.expected_version, str)
            or _VERSION.fullmatch(self.expected_version) is None
        ):
            raise ValueError("expected package version is required and bounded")
        if type(self.manifest) is not tuple or not self.manifest:
            raise ValueError("package manifest must be a non-empty tuple")
        if len(self.manifest) > MAX_PACKAGE_FILE_COUNT:
            raise ValueError("package manifest has too many files")
        if any(type(item) is not ExpectedPackageFile for item in self.manifest):
            raise TypeError("package manifest entries must be ExpectedPackageFile")
        paths = tuple(item.relative_path for item in self.manifest)
        if paths != tuple(sorted(paths)) or len(set(paths)) != len(paths):
            raise ValueError("package manifest paths must be sorted and unique")
        if f"{self.package_name}/__init__.py" not in paths:
            raise ValueError("package manifest must include the package initializer")

    @classmethod
    def from_manifest(
        cls,
        package_name: str,
        approved_root: str | Path,
        expected_version: str,
        manifest: Mapping[str, str | tuple[str, int] | ExpectedPackageFile],
    ) -> PackageTrustBinding:
        """Build a binding from host-owned relative paths and digests."""

        if len(manifest) > MAX_PACKAGE_FILE_COUNT:
            raise ValueError("package manifest has too many files")
        entries: list[ExpectedPackageFile] = []
        for relative_path, value in manifest.items():
            if isinstance(value, ExpectedPackageFile):
                if value.relative_path != relative_path:
                    raise ValueError("manifest key does not match package file path")
                entries.append(value)
            elif isinstance(value, str):
                entries.append(ExpectedPackageFile(relative_path, value))
            elif (
                isinstance(value, tuple)
                and len(value) == 2
                and isinstance(value[0], str)
                and type(value[1]) is int
            ):
                entries.append(ExpectedPackageFile(relative_path, value[0], value[1]))
            else:
                raise TypeError("manifest values must be digests or package file entries")
        return cls(
            package_name,
            Path(approved_root),
            expected_version,
            tuple(sorted(entries, key=lambda item: item.relative_path)),
        )

    @property
    def manifest_by_path(self) -> dict[str, ExpectedPackageFile]:
        return {item.relative_path: item for item in self.manifest}


@dataclass(frozen=True, slots=True)
class VerifiedFile:
    """Identity captured for one expected file descriptor."""

    relative_path: str
    path: Path
    device: int
    inode: int
    size: int
    modified_ns: int
    digest: str
    link_count: int = 1


@dataclass(frozen=True, slots=True)
class PackageIdentity:
    """The bounded identity captured before a verified import transaction."""

    binding: PackageTrustBinding
    package_origin: Path
    package_root: Path
    files: tuple[VerifiedFile, ...]
    aggregate_bytes: int
    root_device: int
    root_inode: int
    root_modified_ns: int


class _VerifiedTransaction:
    """Private authority graph for one verified package import transaction."""

    def __init__(self, identity: PackageIdentity) -> None:
        self.identity = identity
        self.package_name = identity.binding.package_name
        self.sources: dict[str, str] = {}
        self.native: dict[str, str] = {}
        self.modules: dict[str, ModuleType] = {}
        self.shims: dict[str, ModuleType] = {}
        self.created_modules = self.modules
        self.owner_thread_id = get_ident()
        self.owner_task = _current_task()
        self.token = object()
        self.active = True
        self.awaiting = False
        self.builtins: dict[str, object] = dict(vars(builtins))
        self.builtins["__import__"] = self._import_builtin
        native_members = _native_members(identity.binding)
        self.native.update(native_members)
        for item in identity.files:
            if item.relative_path in native_members.values():
                continue
            if not item.relative_path.endswith(".py"):
                continue
            stem = item.relative_path.removesuffix(".py")
            fullname = stem.replace("/", ".")
            self.sources[fullname] = item.relative_path
            if stem.endswith("/__init__"):
                self.sources[stem[: -len("/__init__")].replace("/", ".")] = item.relative_path
        self.finder = _VerifiedPackageFinder(self)

    def import_module(self, fullname: str) -> ModuleType:
        if fullname in self.sources:
            return self._load_module(fullname)
        if fullname in self.native:
            return self._load_native_module(fullname)
        if fullname == "importlib":
            return self._private_importlib()
        if _non_stdlib_import(fullname):
            raise PackageTrustError("optional package imported unbound dependency")
        return _trusted_stdlib_module(self, fullname)

    def _private_importlib(self) -> ModuleType:
        existing = self.modules.get("importlib")
        if existing is not None:
            return existing
        module = ModuleType("importlib")
        module.__package__ = "importlib"
        module.__dict__["__builtins__"] = self.builtins
        module.__dict__["__verified_transaction__"] = self
        module.__dict__["import_module"] = self._import_module_api
        self.modules["importlib"] = module
        return module

    def _import_module_api(self, name: str, package: str | None = None) -> ModuleType:
        if not isinstance(name, str):
            raise TypeError("module name must be a string")
        if name.startswith("."):
            if not isinstance(package, str) or not package:
                raise TypeError("package is required for a relative import")
            level = len(name) - len(name.lstrip("."))
            name = _resolve_import_name(name[level:], {"__package__": package}, level)
        return self.import_module(name)

    def _load_module(self, fullname: str) -> ModuleType:
        existing = self.modules.get(fullname)
        if existing is not None:
            return existing
        source = self.sources.get(fullname)
        if source is None:
            raise PackageTrustError("optional package requested an unbound module")
        is_package = source.endswith("/__init__.py")
        module = ModuleType(fullname)
        self.modules[fullname] = module
        module.__file__ = str(self.identity.binding.approved_root / source)
        module.__package__ = fullname if is_package else fullname.rpartition(".")[0]
        module.__loader__ = _PrivateModuleLoader(self, fullname, source)
        module.__spec__ = importlib.machinery.ModuleSpec(
            fullname, module.__loader__, is_package=is_package
        )
        if is_package:
            module.__path__ = [
                str(self.identity.binding.approved_root / source).removesuffix(
                    "/__init__.py"
                )
            ]
        module.__dict__["__builtins__"] = self.builtins
        module.__dict__["__verified_transaction__"] = self
        try:
            source_bytes = read_verified_bytes(self.identity, source)
            code = compile(source_bytes, module.__file__, "exec")
            exec(code, module.__dict__)
        except PackageTrustError:
            self.modules.pop(fullname, None)
            raise
        except Exception as error:
            self.modules.pop(fullname, None)
            raise PackageTrustError("optional package import failed") from error
        return module

    def _load_native_module(self, fullname: str) -> ModuleType:
        existing = self.modules.get(fullname)
        if existing is not None:
            return existing
        relative = self.native.get(fullname)
        if relative is None:
            raise PackageTrustError("optional package requested an unbound native module")
        # Re-check the captured identity and the descriptor/RECORD boundary
        # immediately before any native code is initialized.
        if not identity_matches(self.identity):
            raise PackageTrustError("optional package identity changed")
        try:
            # ExtensionFileLoader reopens its pathname.  Never give it the
            # mutable package path after verification; execute a private,
            # host-owned copy of the descriptor-verified bytes instead.
            verified = read_verified_bytes(self.identity, relative)
            with tempfile.TemporaryDirectory(prefix="study-agent-native-") as directory:
                artifact = Path(directory) / Path(relative).name
                descriptor = os.open(
                    artifact,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    stat.S_IRUSR | stat.S_IWUSR,
                )
                try:
                    offset = 0
                    while offset < len(verified):
                        offset += os.write(descriptor, verified[offset:])
                    os.fsync(descriptor)
                finally:
                    with suppress(OSError):
                        os.close(descriptor)
                loader = importlib.machinery.ExtensionFileLoader(fullname, str(artifact))
                spec = importlib.machinery.ModuleSpec(
                    fullname, loader, origin=str(artifact), is_package=False
                )
                module = loader.create_module(spec)
                if not isinstance(module, ModuleType):
                    raise PackageTrustError("optional native module could not be created")
                self.modules[fullname] = module
                module.__loader__ = loader
                module.__spec__ = spec
                module.__package__ = fullname.rpartition(".")[0]
                loader.exec_module(module)
                if module.__name__ != fullname:
                    raise PackageTrustError("optional native module identity changed")
                if not identity_matches(self.identity):
                    raise PackageTrustError("optional package identity changed")
                return module
        except PackageTrustError:
            self.modules.pop(fullname, None)
            raise
        except BaseException as error:
            self.modules.pop(fullname, None)
            raise PackageTrustError("optional native module import failed") from error

    def _import_builtin(
        self,
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: tuple[str, ...] | list[str] | None = None,
        level: int = 0,
    ) -> ModuleType:
        del locals
        fullname = _resolve_import_name(name, globals, level)
        module = self.import_module(fullname)
        if fromlist:
            for item in fromlist:
                if item == "*":
                    if "." in fullname:
                        parent_name, _, child_name = fullname.rpartition(".")
                        parent = self.import_module(parent_name)
                        setattr(parent, child_name, module)
                    continue
                child = f"{fullname}.{item}"
                if child in self.sources or child in self.native:
                    child_module = self.import_module(child)
                    setattr(module, item, child_module)
            return module
        root_name = fullname.partition(".")[0]
        root_module = self.import_module(root_name)
        if "." in fullname:
            parent_name, _, child_name = fullname.rpartition(".")
            parent = self.import_module(parent_name)
            setattr(parent, child_name, module)
        return root_module


class _PrivateModuleLoader(importlib.abc.Loader):
    def __init__(self, transaction: _VerifiedTransaction, fullname: str, source: str) -> None:
        self.transaction = transaction
        self.fullname = fullname
        self.source = source

    def create_module(self, _spec: object) -> ModuleType:
        return self.transaction.modules[self.fullname]

    def exec_module(self, _module: ModuleType) -> None:
        return None


class _ModuleShim(ModuleType):
    """Importlib-visible inert compatibility module with no authority."""

    def __init__(self, fullname: str) -> None:
        super().__init__(fullname)


_TRANSACTIONS: dict[str, _VerifiedTransaction] = {}
_FINDERS: dict[str, importlib.abc.MetaPathFinder] = {}
_TRANSACTION_LOCK = RLock()


def validate_distribution(
    binding: PackageTrustBinding,
    _distribution: object | None = None,
    _spec: object | None = None,
) -> PackageIdentity:
    """Validate a host binding using only descriptor-anchored local evidence.

    The legacy arguments remain accepted for source compatibility, but are
    deliberately ignored.  Calling importlib.metadata, find_spec, or any
    distribution callback before this function has established trust would
    give mutable application hooks authority over the decision.
    """

    if not isinstance(binding, PackageTrustBinding):
        raise PackageTrustError("package trust binding is unavailable")
    root = _validated_root(binding.approved_root)
    root_stat = _snapshot_root(root)
    package_root = root / binding.package_name
    package_origin = package_root / "__init__.py"
    _reject_symlink_ancestors(root, package_origin)
    expected = binding.manifest_by_path
    listed = _distribution_paths(binding, root)
    if listed is None or listed != set(expected):
        raise PackageTrustError("package distribution RECORD is not host-bound")
    snapshots: list[VerifiedFile] = []
    aggregate = 0
    for item in binding.manifest:
        path = root / item.relative_path
        file_identity = _snapshot_file(item.relative_path, path, item, root)
        if file_identity is None:
            raise PackageTrustError("package file identity is unavailable")
        aggregate += file_identity.size
        if aggregate > MAX_PACKAGE_AGGREGATE_BYTES:
            raise PackageTrustError("package identity is oversized")
        snapshots.append(file_identity)
    if not _root_stat_matches(root, root_stat):
        raise PackageTrustError("approved package root changed")
    identity = PackageIdentity(
        binding,
        package_origin,
        package_root,
        tuple(snapshots),
        aggregate,
        root_stat.st_dev,
        root_stat.st_ino,
        root_stat.st_mtime_ns,
    )
    if serialized_identity_size(identity) > MAX_SERIALIZED_IDENTITY_BYTES:
        raise PackageTrustError("serialized package identity is oversized")
    return identity


def serialize_identity(identity: PackageIdentity) -> bytes:
    """Encode identity as bounded canonical JSON for the worker protocol."""

    if not isinstance(identity, PackageIdentity):
        raise TypeError("package identity is required")
    payload = {
        "aggregate_bytes": identity.aggregate_bytes,
        "binding": {
            "expected_version": identity.binding.expected_version,
            "manifest": [
                [item.relative_path, item.digest, item.size]
                for item in identity.binding.manifest
            ],
            "package_name": identity.binding.package_name,
            "approved_root": str(identity.binding.approved_root),
        },
        "files": [
            [
                item.relative_path,
                str(item.path),
                item.device,
                item.inode,
                item.size,
                item.modified_ns,
                item.digest,
                item.link_count,
            ]
            for item in identity.files
        ],
        "package_origin": str(identity.package_origin),
        "package_root": str(identity.package_root),
        "root": [identity.root_device, identity.root_inode, identity.root_modified_ns],
        "schema": _IDENTITY_SCHEMA,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    if len(encoded) > MAX_SERIALIZED_IDENTITY_BYTES:
        raise PackageTrustError("serialized package identity is oversized")
    return encoded


def deserialize_identity(encoded: bytes) -> PackageIdentity:
    """Decode and structurally validate the fixed worker identity message."""

    if not isinstance(encoded, bytes) or len(encoded) > MAX_SERIALIZED_IDENTITY_BYTES:
        raise PackageTrustError("serialized package identity is oversized")
    try:
        value = json.loads(
            encoded.decode("ascii"), object_pairs_hook=_reject_duplicate_json_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        raise PackageTrustError("serialized package identity is invalid") from None
    if not isinstance(value, dict) or value.get("schema") != _IDENTITY_SCHEMA:
        raise PackageTrustError("serialized package identity is invalid")
    binding_value = value.get("binding")
    if not isinstance(binding_value, dict):
        raise PackageTrustError("serialized package identity is invalid")
    package_name = binding_value.get("package_name")
    approved_root = binding_value.get("approved_root")
    expected_version = binding_value.get("expected_version")
    manifest_value = binding_value.get("manifest")
    if (
        not isinstance(package_name, str)
        or not isinstance(approved_root, str)
        or not isinstance(expected_version, str)
        or not isinstance(manifest_value, list)
    ):
        raise PackageTrustError("serialized package identity is invalid")
    manifest: dict[str, str | tuple[str, int]] = {}
    for item in manifest_value:
        if not isinstance(item, list) or len(item) != 3:
            raise PackageTrustError("serialized package identity is invalid")
        relative, digest, size = item
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise PackageTrustError("serialized package identity is invalid")
        if size is None:
            manifest[relative] = digest
        elif type(size) is int:
            manifest[relative] = (digest, size)
        else:
            raise PackageTrustError("serialized package identity is invalid")
    try:
        binding = PackageTrustBinding.from_manifest(
            package_name, approved_root, expected_version, manifest
        )
    except (TypeError, ValueError, OSError):
        raise PackageTrustError("serialized package identity is invalid") from None
    files_value = value.get("files")
    root_value = value.get("root")
    aggregate = value.get("aggregate_bytes")
    origin = value.get("package_origin")
    package_root = value.get("package_root")
    if (
        not isinstance(files_value, list)
        or not isinstance(root_value, list)
        or len(root_value) != 3
        or type(aggregate) is not int
        or not isinstance(origin, str)
        or not isinstance(package_root, str)
        or any(type(item) is not int or item < 0 for item in root_value)
    ):
        raise PackageTrustError("serialized package identity is invalid")
    files: list[VerifiedFile] = []
    for item in files_value:
        if not isinstance(item, list) or len(item) != 8:
            raise PackageTrustError("serialized package identity is invalid")
        relative, path, device, inode, size, modified, digest, links = item
        if (
            not isinstance(relative, str)
            or not isinstance(path, str)
            or any(
                type(value) is not int or value < 0
                for value in (device, inode, size, modified, links)
            )
            or not isinstance(digest, str)
            or not _SHA256.fullmatch(digest)
            or links != 1
        ):
            raise PackageTrustError("serialized package identity is invalid")
        try:
            normalized = _relative_path(relative)
            expected = binding.manifest_by_path[normalized]
        except (KeyError, ValueError):
            raise PackageTrustError("serialized package identity is invalid") from None
        if expected.digest != digest or (expected.size is not None and expected.size != size):
            raise PackageTrustError("serialized package identity is invalid")
        files.append(
            VerifiedFile(normalized, Path(path), device, inode, size, modified, digest, links)
        )
    files.sort(key=lambda item: item.relative_path)
    expected_paths = tuple(item.relative_path for item in binding.manifest)
    if tuple(item.relative_path for item in files) != expected_paths:
        raise PackageTrustError("serialized package identity is invalid")
    expected_root = binding.approved_root
    if (
        Path(origin) != expected_root / package_name / "__init__.py"
        or Path(package_root) != expected_root / package_name
        or any(item.path != expected_root / item.relative_path for item in files)
        or aggregate != sum(item.size for item in files)
    ):
        raise PackageTrustError("serialized package identity is invalid")
    identity = PackageIdentity(
        binding,
        Path(origin),
        Path(package_root),
        tuple(files),
        aggregate,
        root_value[0],
        root_value[1],
        root_value[2],
    )
    if serialize_identity(identity) != encoded:
        raise PackageTrustError("serialized package identity is not canonical")
    return identity


def serialized_identity_size(identity: PackageIdentity) -> int:
    """Return the bounded canonical wire size used across a process boundary."""

    try:
        return len(serialize_identity(identity))
    except (OSError, OverflowError, TypeError, ValueError, PackageTrustError):
        return MAX_SERIALIZED_IDENTITY_BYTES + 1


def identity_matches(identity: PackageIdentity) -> bool:
    """Check root and every captured file identity without import hooks."""

    if serialized_identity_size(identity) > MAX_SERIALIZED_IDENTITY_BYTES:
        return False
    try:
        root = _validated_root(identity.binding.approved_root)
        root_stat = os.stat(root, follow_symlinks=False)
        if not _root_stat_values_match(root_stat, identity):
            return False
    except (OSError, RuntimeError, TypeError, ValueError, PackageTrustError):
        return False
    expected = identity.binding.manifest_by_path
    try:
        if _native_members(identity.binding) and _distribution_paths(
            identity.binding, root
        ) != set(expected):
            return False
    except (OSError, RuntimeError, TypeError, ValueError, PackageTrustError):
        return False
    return all(
        (
            current := _snapshot_file(
                item.relative_path, item.path, expected[item.relative_path], root
            )
        )
        is not None
        and current == item
        for item in identity.files
    )


def reject_preloaded_namespace(package_name: str) -> None:
    """Reject exact/prefixed modules unless this verifier owns the transaction."""

    names = {
        name
        for name in sys.modules
        if name == package_name or name.startswith(f"{package_name}.")
    }
    if not names:
        return
    transaction = _TRANSACTIONS.get(package_name)
    shim_names = set(transaction.shims) if transaction is not None else set()
    if transaction is None or names - shim_names:
        raise PackageTrustError("optional package namespace is preloaded")


def load_verified_package(identity: PackageIdentity) -> ModuleType:
    """Import fresh verified bytes into a transaction-private module graph."""

    with _TRANSACTION_LOCK:
        return _load_verified_package(identity)


def use_verified_package(
    identity: PackageIdentity, operation: Callable[[ModuleType], object],
) -> object:
    """Use verified package exports while the trust transaction is held.

    Optional package exports are mutable Python objects.  Keeping the load,
    export lookup, and sensitive operation in one transaction prevents callers
    from accidentally treating a module returned by the verifier as an
    immutable authority after the lock has been released.
    """

    if not callable(operation):
        raise TypeError("verified package operation must be callable")
    operation_call = type(operation).__call__
    if inspect.iscoroutinefunction(operation) or inspect.iscoroutinefunction(operation_call):
        return _run_verified_operation(identity, operation)
    _TRANSACTION_LOCK.acquire()
    transaction: _VerifiedTransaction | None = None
    try:
        module = _load_verified_package(identity)
        transaction = _TRANSACTIONS.get(identity.binding.package_name)
        if transaction is None:
            raise PackageTrustError("optional package verifier is unavailable")
        transaction.active = True
        _assert_transaction_namespace(identity.binding.package_name)
        result = operation(module)
        if inspect.isawaitable(result):
            raise PackageTrustError(
                "verified async operation must be declared async"
            )
        _assert_transaction_namespace(identity.binding.package_name)
        _finish_transaction(transaction)
        _TRANSACTION_LOCK.release()
        return result
    except BaseException:
        if transaction is not None:
            _finish_transaction(transaction)
        _TRANSACTION_LOCK.release()
        raise


async def _run_verified_operation(
    identity: PackageIdentity, operation: Callable[[ModuleType], object]
) -> object:
    """Acquire authority only when the returned coroutine is actually awaited."""

    _TRANSACTION_LOCK.acquire()
    transaction: _VerifiedTransaction | None = None
    try:
        module = _load_verified_package(identity)
        transaction = _TRANSACTIONS.get(identity.binding.package_name)
        if transaction is None:
            raise PackageTrustError("optional package verifier is unavailable")
        transaction.active = True
        transaction.owner_task = _current_task()
        _assert_transaction_namespace(identity.binding.package_name)
        result = operation(module)
        if not inspect.isawaitable(result):
            raise PackageTrustError("verified async operation returned no awaitable")
        transaction.awaiting = True
        value = await result
        if _TRANSACTIONS.get(transaction.package_name) is not transaction:
            raise PackageTrustError("optional package transaction changed")
        if not identity_matches(transaction.identity):
            raise PackageTrustError("optional package identity changed")
        _assert_transaction_namespace(transaction.package_name)
        return value
    finally:
        if transaction is not None:
            _finish_transaction(transaction)
        _TRANSACTION_LOCK.release()


def _load_verified_package(identity: PackageIdentity) -> ModuleType:
    binding = identity.binding
    if not identity_matches(identity):
        raise PackageTrustError("optional package identity changed")
    reject_preloaded_namespace(binding.package_name)
    native_names = _native_members(binding)
    if any(name in sys.modules for name in native_names):
        raise PackageTrustError("optional package namespace is preloaded")
    existing = _TRANSACTIONS.get(binding.package_name)
    if existing is not None:
        if existing.awaiting:
            raise PackageTrustError("optional package transaction is busy")
        _finish_transaction(existing)
    transaction = _VerifiedTransaction(identity)
    _TRANSACTIONS[binding.package_name] = transaction
    _FINDERS[binding.package_name] = transaction.finder
    sys.meta_path.insert(0, transaction.finder)
    try:
        _validate_stdlib_preloads()
        return transaction.import_module(binding.package_name)
    except PackageTrustError:
        _finish_transaction(transaction)
        raise
    except Exception as error:
        _finish_transaction(transaction)
        raise PackageTrustError("optional package import failed") from error


def read_verified_bytes(identity: PackageIdentity, relative_path: str) -> bytes:
    """Read exact bytes from the captured file descriptor identity."""

    expected = identity.binding.manifest_by_path.get(relative_path)
    if expected is None:
        raise PackageTrustError("optional package requested an unbound file")
    captured = next(
        (item for item in identity.files if item.relative_path == relative_path), None
    )
    if captured is None or not _root_identity_matches(identity):
        raise PackageTrustError("optional package file changed")
    path = identity.binding.approved_root / expected.relative_path
    try:
        _reject_symlink_ancestors(identity.binding.approved_root, path)
        descriptor = _open_verified(path)
    except (OSError, RuntimeError, TypeError, ValueError, PackageTrustError) as error:
        raise PackageTrustError("optional package file could not be opened") from error
    try:
        before = os.fstat(descriptor)
        if not _file_stat_matches(before, captured):
            raise PackageTrustError("optional package file changed")
        data = bytearray()
        while True:
            chunk = os.read(descriptor, IDENTITY_READ_SIZE)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_IDENTITY_FILE_BYTES:
                raise PackageTrustError("optional package file is oversized")
        after = os.fstat(descriptor)
        digest = sha256(data).hexdigest()
        if (
            not _file_stat_matches(after, captured)
            or digest != expected.digest
            or (expected.size is not None and len(data) != expected.size)
            or not _root_identity_matches(identity)
        ):
            raise PackageTrustError("optional package file changed")
        return bytes(data)
    except OSError as error:
        raise PackageTrustError("optional package file could not be read") from error
    finally:
        with suppress(OSError):
            os.close(descriptor)


class _VerifiedPackageFinder(importlib.abc.MetaPathFinder):
    def __init__(self, transaction: _VerifiedTransaction) -> None:
        self._transaction = transaction
        self._package = transaction.package_name
        self._active = True
        self._sources = transaction.sources
        self.executed_modules = transaction.created_modules

    def find_spec(
        self, fullname: str, _path: Iterable[str] | None = None, _target: ModuleType | None = None
    ) -> importlib.machinery.ModuleSpec | None:
        transaction = self._transaction
        if not transaction.active:
            return None
        current_task = _current_task()
        owns_execution = get_ident() == transaction.owner_thread_id and (
            transaction.owner_task is None or current_task is transaction.owner_task
        )
        if not _has_verified_provenance(transaction) and not owns_execution:
            if fullname in transaction.sources or fullname.startswith(f"{self._package}."):
                raise PackageTrustError("optional package import is transaction-owned")
            return None
        if fullname != self._package and not fullname.startswith(f"{self._package}."):
            if _non_stdlib_import(fullname):
                if not self._active:
                    return None
                source = self._sources.get(fullname)
                if source is None and fullname in transaction.native:
                    transaction.import_module(fullname)
                    return self._shim_spec(fullname, transaction.native[fullname])
                if source is None:
                    raise PackageTrustError("optional package imported unbound dependency")
                return self._shim_spec(fullname, source)
            if not self._active:
                return None
            return _trusted_stdlib_spec(fullname, _path)
        source = self._sources.get(fullname)
        if source is None and fullname in transaction.native:
            transaction.import_module(fullname)
            return self._shim_spec(fullname, transaction.native[fullname])
        if source is None:
            raise PackageTrustError("optional package requested an unbound module")
        return self._shim_spec(fullname, source)

    def _shim_spec(self, fullname: str, source: str) -> importlib.machinery.ModuleSpec:
        self._transaction.import_module(fullname)
        is_package = source.endswith("/__init__.py")
        shim = self._transaction.shims.get(fullname)
        if shim is None:
            shim = _ModuleShim(fullname)
            self._transaction.shims[fullname] = shim
        shim.__package__ = fullname if is_package else fullname.rpartition(".")[0]
        if is_package:
            shim.__path__ = []
        return importlib.machinery.ModuleSpec(
            fullname,
            _ShimLoader(shim),
            is_package=is_package,
        )


class _ShimLoader(importlib.abc.Loader):
    def __init__(self, shim: ModuleType) -> None:
        self.shim = shim

    def create_module(self, _spec: object) -> ModuleType:
        return self.shim

    def exec_module(self, _module: ModuleType) -> None:
        return None


def _distribution_paths(binding: PackageTrustBinding, root: Path) -> set[str] | None:
    expected = binding.manifest_by_path
    native_members = _native_members(binding)
    dist_infos: dict[str, tuple[str, str]] = {}
    for relative in expected:
        parts = relative.split("/")
        if len(parts) >= 2 and parts[-2].endswith(".dist-info") and parts[-1] in {
            "METADATA",
            "RECORD",
        }:
            entry = dist_infos.setdefault(parts[-2], ("", ""))
            dist_infos[parts[-2]] = (
                relative if parts[-1] == "METADATA" else entry[0],
                relative if parts[-1] == "RECORD" else entry[1],
            )
    if not dist_infos:
        # A host manifest is itself an explicit trust authority.  This keeps
        # synthetic host bindings usable while real wheels use RECORD below.
        return None if native_members else set(expected)
    if any(not metadata or not record for metadata, record in dist_infos.values()):
        return None
    owned: dict[str, str] = {}
    distribution_owned: dict[str, set[str]] = {}
    identities: set[str] = set()
    primary_count = 0
    native_packages = {
        policy.package_name.replace("_", "-").lower()
        for relative in native_members.values()
        if (policy := _native_policy_for_path(relative)) is not None
    }
    native_seen: set[str] = set()
    try:
        for dist_name, (metadata_relative, record_relative) in dist_infos.items():
            metadata = _read_bounded_path(root, root / metadata_relative, MAX_METADATA_BYTES)
            name, version = _metadata_identity(metadata)
            identity_key = name.replace("_", "-").lower()
            if identity_key in identities:
                return None
            identities.add(identity_key)
            if identity_key == binding.package_name.replace("_", "-").lower():
                if version != binding.expected_version:
                    return None
                primary_count += 1
            is_native_distribution = identity_key in native_packages
            if is_native_distribution:
                policy = next(
                    (
                        item
                        for item in _NATIVE_PACKAGE_POLICIES
                        if item.package_name.replace("_", "-").lower() == identity_key
                    ),
                    None,
                )
                if policy is None or version != policy.expected_version:
                    return None
                wheel_relative = f"{dist_name}/WHEEL"
                if wheel_relative not in expected or not _validate_native_wheel(
                    _read_bounded_path(root, root / wheel_relative, MAX_METADATA_BYTES),
                    native_members,
                    policy,
                ):
                    return None
                native_seen.add(identity_key)
            record = _read_bounded_path(root, root / record_relative, MAX_RECORD_BYTES)
            metadata_root = root / dist_name
            allowed_launchers = _entry_point_names(root, metadata_root)
            seen: set[str] = set()
            if len(record.splitlines()) > MAX_RECORD_ENTRIES:
                return None
            for raw_line in record.splitlines(keepends=True):
                if len(raw_line) > MAX_RECORD_LINE_BYTES:
                    return None
                line = raw_line.rstrip(b"\r\n")
                if not line:
                    return None
                try:
                    row = next(csv.reader([line.decode("utf-8")]))
                except (UnicodeDecodeError, csv.Error, StopIteration):
                    return None
                if len(row) != 3 or not row[0] or row[0] in seen:
                    return None
                seen.add(row[0])
                raw = row[0]
                if any(ord(character) < 32 or character == "\\" for character in raw):
                    return None
                target = root / raw
                try:
                    normalized = _relative_to_root(target.resolve(strict=False), root)
                except (OSError, RuntimeError, ValueError):
                    normalized = None
                if normalized is None or _has_symlink_ancestor(root, target):
                    if _is_installer_launcher(raw, root, allowed_launchers):
                        if is_native_distribution:
                            return None
                        continue
                    return None
                if normalized in owned and owned[normalized] != dist_name:
                    return None
                if is_native_distribution and not _native_record_row_matches(
                    row,
                    normalized,
                    record_relative,
                    expected,
                    root,
                ):
                    return None
                owned[normalized] = dist_name
                distribution_owned.setdefault(identity_key, set()).add(normalized)
        if (
            primary_count != 1
            or set(owned) != set(expected)
            or native_seen != native_packages
        ):
            return None
        for relative in native_members.values():
            policy = _native_policy_for_path(relative)
            if policy is None:
                return None
            owner = policy.package_name.replace("_", "-").lower()
            if relative not in distribution_owned.get(owner, set()):
                return None
        return set(owned)
    except (OSError, RuntimeError, TypeError, ValueError, PackageTrustError):
        return None


def _find_dist_info(root: Path, package_name: str) -> Path | None:
    prefix = package_name.replace("_", "-").lower() + "-"
    found: Path | None = None
    count = 0
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                count += 1
                if count > MAX_PACKAGE_FILE_COUNT:
                    return None
                if not entry.name.endswith(".dist-info"):
                    continue
                if not entry.name[:-10].lower().startswith(prefix):
                    continue
                candidate = root / entry.name
                if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                    return None
                if found is not None:
                    return None
                found = candidate
    except OSError:
        return None
    return found


def _metadata_identity(raw: bytes) -> tuple[str, str]:
    values: dict[str, str] = {}
    for line in raw.splitlines(keepends=True):
        if len(line) > MAX_METADATA_LINE_BYTES:
            raise PackageTrustError("package METADATA line is oversized")
        decoded = line.rstrip(b"\r\n").decode("utf-8")
        if not decoded:
            continue
        key, separator, value = decoded.partition(":")
        if not separator or key not in {"Name", "Version"} or key in values:
            if key in {"Name", "Version"}:
                raise PackageTrustError("package METADATA has duplicate fields")
            continue
        values[key] = value.strip()
    name = values.get("Name", "")
    version = values.get("Version", "")
    if not name or not version or _VERSION.fullmatch(version) is None:
        raise PackageTrustError("package METADATA identity is invalid")
    return name, version


def _validate_metadata(raw: bytes, binding: PackageTrustBinding) -> None:
    name, version = _metadata_identity(raw)
    expected_name = binding.package_name.replace("_", "-").lower()
    if name.replace("_", "-").lower() != expected_name:
        raise PackageTrustError("package METADATA name is not host-bound")
    if version != binding.expected_version:
        raise PackageTrustError("package METADATA version is not host-bound")


def _entry_point_names(root: Path, metadata_root: Path) -> set[str]:
    path = metadata_root / "entry_points.txt"
    if not _path_exists_without_symlink(root, path):
        return set()
    raw = _read_bounded_path(root, path, MAX_METADATA_BYTES)
    names: set[str] = set()
    section = ""
    for line in raw.splitlines(keepends=True):
        if len(line) > MAX_METADATA_LINE_BYTES:
            raise PackageTrustError("package entry-point line is oversized")
        decoded = line.rstrip(b"\r\n").decode("utf-8")
        stripped = decoded.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if section != "console_scripts":
            continue
        name, separator, target = stripped.partition("=")
        if not separator or not _LAUNCHER.fullmatch(name.strip()) or not target.strip():
            raise PackageTrustError("package entry-point metadata is invalid")
        normalized = name.strip()
        if normalized in names:
            raise PackageTrustError("package entry-point metadata is duplicated")
        names.add(normalized)
    return names


def _is_installer_launcher(raw: str, root: Path, allowed: set[str]) -> bool:
    try:
        relative = PurePosixPath(raw)
    except (TypeError, ValueError):
        return False
    parts = relative.parts
    if (
        not parts
        or len(parts) < 3
        or parts[-2] != "bin"
        or any(part != ".." for part in parts[:-2])
        or parts[-1] not in allowed
    ):
        return False
    name = parts[-1]
    try:
        resolved = (root.joinpath(*parts)).resolve(strict=True)
        for parent in (root.parent, root.parent.parent, root.parent.parent.parent):
            launcher = parent / "bin" / name
            if resolved != launcher or _has_symlink_ancestor(parent / "bin", launcher):
                continue
            metadata = os.stat(launcher, follow_symlinks=False)
            return stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1 and bool(
                metadata.st_mode & stat.S_IXUSR
            )
    except (OSError, RuntimeError, ValueError):
        return False
    return False


def _native_suffix(relative: str) -> str | None:
    suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    for suffix in sorted(suffixes, key=len, reverse=True):
        if relative.endswith(suffix):
            return suffix
    return ".so" if relative.endswith(".so") else None


def _native_members(binding: PackageTrustBinding) -> dict[str, str]:
    members: dict[str, str] = {}
    for relative in binding.manifest_by_path:
        suffix = _native_suffix(relative)
        if suffix is None:
            continue
        policy = _native_policy_for_path(relative)
        if policy is None:
            raise PackageTrustError("optional package native member is not allowlisted")
        fullname = relative.removesuffix(suffix).replace("/", ".")
        if fullname in members:
            raise PackageTrustError("optional package native member is duplicated")
        members[fullname] = relative
    return members


def _native_policy_for_path(relative: str) -> _NativePackagePolicy | None:
    for policy in _NATIVE_PACKAGE_POLICIES:
        if any(
            relative == f"{policy.member}{suffix}"
            for suffix in importlib.machinery.EXTENSION_SUFFIXES
            if suffix != ".so"
        ):
            return policy
    return None


def _validate_native_wheel(
    raw: bytes,
    native_members: Mapping[str, str],
    policy: _NativePackagePolicy,
) -> bool:
    values: dict[str, list[str]] = {}
    for line in raw.splitlines(keepends=True):
        if len(line) > MAX_METADATA_LINE_BYTES:
            return False
        decoded = line.rstrip(b"\r\n").decode("utf-8")
        if not decoded:
            continue
        key, separator, value = decoded.partition(":")
        if not separator or key not in {"Root-Is-Purelib", "Tag"}:
            continue
        values.setdefault(key, []).append(value.strip())
    if values.get("Root-Is-Purelib") != ["false"]:
        return False
    tags = values.get("Tag", [])
    if len(tags) != 1:
        return False
    parts = tags[0].split("-")
    if len(parts) != 3:
        return False
    interpreter, abi, platform_tag = parts
    if sys.implementation.name != "cpython":
        return False
    expected_interpreter = f"cp{sys.version_info.major}{sys.version_info.minor}"
    if interpreter != expected_interpreter or abi not in {expected_interpreter, "abi3"}:
        return False
    if not _wheel_platform_compatible(platform_tag):
        return False
    native_relative = next(
        (
            relative
            for fullname, relative in native_members.items()
            if fullname == policy.member.replace("/", ".")
        ),
        None,
    )
    if native_relative is None:
        return False
    suffix = _native_suffix(native_relative)
    if suffix is None or suffix == ".so":
        return False
    if suffix.startswith(".abi3") != (abi == "abi3"):
        return False
    if suffix.startswith(f".cpython-{sys.version_info.major}{sys.version_info.minor}") != (
        abi == expected_interpreter
    ):
        return False
    return True


def _wheel_platform_compatible(value: str) -> bool:
    current = sysconfig.get_platform().replace("-", "_").replace(".", "_").lower()
    candidate = value.replace(".", "_").lower()
    if candidate == current:
        return True
    current_match = re.fullmatch(r"macosx_(\d+)_(\d+)_([a-z0-9_]+)", current)
    candidate_match = re.fullmatch(r"macosx_(\d+)_(\d+)_([a-z0-9_]+)", candidate)
    if current_match is None or candidate_match is None:
        return False
    if candidate_match.group(3) == "universal2" and current_match.group(3) in {
        "arm64",
        "x86_64",
    }:
        return (
            int(candidate_match.group(1)),
            int(candidate_match.group(2)),
        ) <= (
            int(current_match.group(1)),
            int(current_match.group(2)),
        )
    return (
        candidate_match.group(3) == current_match.group(3)
        and (int(candidate_match.group(1)), int(candidate_match.group(2)))
        <= (int(current_match.group(1)), int(current_match.group(2)))
    )


def _native_record_row_matches(
    row: list[str],
    normalized: str,
    record_relative: str,
    expected: Mapping[str, ExpectedPackageFile],
    root: Path,
) -> bool:
    item = expected.get(normalized)
    if item is None:
        return False
    digest, size = row[1], row[2]
    if normalized == record_relative and digest == "" and size == "":
        return True
    if not digest.startswith("sha256=") or not size.isdigit():
        return False
    expected_size = item.size
    if expected_size is None:
        try:
            metadata = os.stat(root / normalized, follow_symlinks=False)
            expected_size = metadata.st_size
        except OSError:
            return False
    if size != str(expected_size):
        return False
    encoded = base64.urlsafe_b64encode(bytes.fromhex(item.digest)).decode("ascii").rstrip("=")
    return digest == f"sha256={encoded}"


def _validated_root(root: Path) -> Path:
    try:
        if root.is_symlink() or not root.is_dir() or root.resolve(strict=True) != root:
            raise PackageTrustError("approved package root is not immutable")
        _reject_symlink_ancestors(root, root)
    except (OSError, RuntimeError, ValueError, PackageTrustError):
        raise PackageTrustError("approved package root is unavailable") from None
    return root


def _snapshot_root(root: Path) -> os.stat_result:
    try:
        value = os.stat(root, follow_symlinks=False)
    except OSError:
        raise PackageTrustError("approved package root is unavailable") from None
    if not stat.S_ISDIR(value.st_mode):
        raise PackageTrustError("approved package root is unavailable")
    return value


def _snapshot_file(
    relative_path: str, path: Path, expected: ExpectedPackageFile, root: Path
) -> VerifiedFile | None:
    try:
        _reject_symlink_ancestors(root, path)
        descriptor = _open_verified(path)
    except (OSError, RuntimeError, TypeError, ValueError, PackageTrustError):
        return None
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_size > MAX_IDENTITY_FILE_BYTES
            or before.st_nlink != 1
        ):
            return None
        digest = sha256()
        while True:
            chunk = os.read(descriptor, IDENTITY_READ_SIZE)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
        value = digest.hexdigest()
        if (
            not _file_stat_values_match(before, after)
            or value != expected.digest
            or (expected.size is not None and before.st_size != expected.size)
        ):
            return None
        return VerifiedFile(
            relative_path,
            path,
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            value,
            before.st_nlink,
        )
    except OSError:
        return None
    finally:
        with suppress(OSError):
            os.close(descriptor)


def _read_bounded_path(root: Path, path: Path, limit: int) -> bytes:
    _reject_symlink_ancestors(root, path)
    descriptor = _open_verified(path)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise PackageTrustError("package metadata file is invalid")
        data = bytearray()
        while True:
            chunk = os.read(descriptor, min(IDENTITY_READ_SIZE, limit + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > limit:
                raise PackageTrustError("package metadata file is oversized")
        after = os.fstat(descriptor)
        if not _file_stat_values_match(metadata, after):
            raise PackageTrustError("package metadata file changed")
        return bytes(data)
    finally:
        with suppress(OSError):
            os.close(descriptor)


def _path_exists_without_symlink(root: Path, path: Path) -> bool:
    try:
        _reject_symlink_ancestors(root, path)
        return path.is_file()
    except (OSError, RuntimeError, ValueError, PackageTrustError):
        return False


def _open_verified(path: Path) -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    return os.open(path, flags)


def _relative_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("package manifest path must be relative POSIX text")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("package manifest path must stay under the approved root")
    return path.as_posix()


def _relative_to_root(path: Path, root: Path) -> str | None:
    try:
        return _relative_path(path.relative_to(root).as_posix())
    except (ValueError, TypeError):
        return None


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _reject_symlink_ancestors(root: Path, path: Path) -> None:
    if not root.is_absolute() or not _is_under(path, root):
        raise PackageTrustError("package path escaped approved root")
    current = root
    if current.is_symlink():
        raise PackageTrustError("package root is symlinked")
    relative = path.relative_to(root)
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise PackageTrustError("package path has a symlinked ancestor")


def _has_symlink_ancestor(root: Path, path: Path) -> bool:
    try:
        if not _is_under(path, root):
            return True
        _reject_symlink_ancestors(root, path)
    except (OSError, RuntimeError, ValueError, PackageTrustError):
        return True
    return False


def _root_identity_matches(identity: PackageIdentity) -> bool:
    try:
        root = _validated_root(identity.binding.approved_root)
        return _root_stat_values_match(os.stat(root, follow_symlinks=False), identity)
    except (OSError, RuntimeError, ValueError, PackageTrustError):
        return False


def _root_stat_matches(root: Path, expected: os.stat_result) -> bool:
    try:
        return _root_stat_values_match(os.stat(root, follow_symlinks=False), expected)
    except OSError:
        return False


def _root_stat_values_match(
    value: os.stat_result, expected: PackageIdentity | os.stat_result
) -> bool:
    if isinstance(expected, PackageIdentity):
        return (
            stat.S_ISDIR(value.st_mode)
            and value.st_dev == expected.root_device
            and value.st_ino == expected.root_inode
            and value.st_mtime_ns == expected.root_modified_ns
        )
    return (
        stat.S_ISDIR(value.st_mode)
        and value.st_dev == expected.st_dev
        and value.st_ino == expected.st_ino
        and value.st_mtime_ns == expected.st_mtime_ns
    )


def _file_stat_matches(value: os.stat_result, expected: VerifiedFile) -> bool:
    return (
        stat.S_ISREG(value.st_mode)
        and value.st_dev == expected.device
        and value.st_ino == expected.inode
        and value.st_size == expected.size
        and value.st_mtime_ns == expected.modified_ns
        and value.st_nlink == expected.link_count == 1
    )


def _file_stat_values_match(before: os.stat_result, after: os.stat_result) -> bool:
    return (
        stat.S_ISREG(before.st_mode)
        and stat.S_ISREG(after.st_mode)
        and before.st_dev == after.st_dev
        and before.st_ino == after.st_ino
        and before.st_size == after.st_size
        and before.st_mtime_ns == after.st_mtime_ns
        and before.st_nlink == after.st_nlink == 1
    )


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _discard_namespace(package_name: str) -> None:
    for name in tuple(sys.modules):
        if name == package_name or name.startswith(f"{package_name}."):
            sys.modules.pop(name, None)


def _discard_loaded_modules(loaded: Mapping[str, ModuleType]) -> None:
    for name, module in loaded.items():
        if sys.modules.get(name) is module:
            sys.modules.pop(name, None)


def _assert_transaction_namespace(package_name: str) -> None:
    transaction = _TRANSACTIONS.get(package_name)
    if transaction is None:
        raise PackageTrustError("optional package verifier is unavailable")
    owned_names = set(transaction.sources) | set(transaction.native)
    if any(
        (
            name in sys.modules
            and sys.modules[name]
            not in {transaction.shims.get(name), transaction.modules.get(name)}
        )
        for name in owned_names
    ):
        raise PackageTrustError("optional package namespace was replaced")


def _isolate_transaction_namespace(package_name: str) -> None:
    transaction = _TRANSACTIONS.get(package_name)
    if transaction is None:
        raise PackageTrustError("optional package verifier is unavailable")
    for name, shim in transaction.shims.items():
        if sys.modules.get(name) is shim:
            sys.modules.pop(name, None)


def _clear_transaction(
    package_name: str, expected: _VerifiedTransaction | None = None
) -> None:
    transaction = _TRANSACTIONS.get(package_name)
    if expected is not None and transaction is not expected:
        return
    transaction = _TRANSACTIONS.pop(package_name, None)
    if transaction is not None:
        for name, shim in transaction.shims.items():
            if sys.modules.get(name) is shim:
                sys.modules.pop(name, None)
        for name, module in transaction.modules.items():
            if sys.modules.get(name) is module:
                sys.modules.pop(name, None)
    finder = _FINDERS.pop(package_name, None)
    if finder is not None:
        with suppress(ValueError):
            sys.meta_path.remove(finder)


def _trusted_stdlib_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    for key in ("stdlib", "platstdlib"):
        value = sysconfig.get_paths().get(key)
        if not isinstance(value, str):
            continue
        try:
            root = Path(value).resolve(strict=True)
        except (OSError, RuntimeError, ValueError):
            continue
        if root.is_dir() and root not in roots:
            roots.append(root)
    return tuple(roots)


_STDLIB_ROOTS = _trusted_stdlib_roots()
_STDLIB_NAMES = frozenset(getattr(sys, "stdlib_module_names", ()))


def _path_under_roots(path: Path, roots: tuple[Path, ...]) -> bool:
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return False
    return any(resolved == root or root in resolved.parents for root in roots)


_TRUSTED_STDLIB_BASELINE = {
    name: module
    for name, module in tuple(sys.modules.items())
    if name.partition(".")[0] in _STDLIB_NAMES
}


def _trusted_stdlib_spec(
    fullname: str, path: Iterable[str] | None,
) -> importlib.machinery.ModuleSpec:
    search_path = list(path) if path is not None else [
        item for item in sys.path if isinstance(item, str)
    ]
    trusted_path = [item for item in search_path if _path_under_roots(Path(item), _STDLIB_ROOTS)]
    for importer in (importlib.machinery.BuiltinImporter, importlib.machinery.FrozenImporter):
        builtin_spec = importer.find_spec(fullname)
        if builtin_spec is not None:
            return builtin_spec
    spec = importlib.machinery.PathFinder.find_spec(fullname, trusted_path or None)
    if spec is None:
        raise PackageTrustError("stdlib module origin is unavailable")
    if spec.origin in {"built-in", "frozen"}:
        return spec
    if not isinstance(spec.origin, str) or not _path_under_roots(Path(spec.origin), _STDLIB_ROOTS):
        raise PackageTrustError("stdlib module origin is untrusted")
    return spec


def _trusted_stdlib_module(
    transaction: _VerifiedTransaction, fullname: str,
) -> ModuleType:
    baseline = _TRUSTED_STDLIB_BASELINE.get(fullname)
    if baseline is not None:
        return baseline
    spec = _trusted_stdlib_spec(fullname, None)
    loader = spec.loader
    if loader is None:
        raise PackageTrustError("stdlib module loader is unavailable")
    module = ModuleType(fullname)
    transaction.modules[fullname] = module
    module.__file__ = str(spec.origin) if isinstance(spec.origin, str) else fullname
    module.__package__ = fullname.rpartition(".")[0]
    module.__loader__ = loader
    module.__spec__ = spec
    module.__dict__["__builtins__"] = transaction.builtins
    module.__dict__["__verified_transaction__"] = transaction
    try:
        loader.exec_module(module)
    except Exception as error:
        transaction.modules.pop(fullname, None)
        raise PackageTrustError("stdlib module import failed") from error
    return module


def _resolve_import_name(
    name: str, globals: Mapping[str, object] | None, level: int,
) -> str:
    if level == 0:
        return name
    package = globals.get("__package__") if globals is not None else None
    if not isinstance(package, str) or not package:
        raise ImportError("relative import requires a package")
    bits = package.split(".")
    if level > len(bits):
        raise ImportError("attempted relative import beyond top-level package")
    base = ".".join(bits[: len(bits) - level + 1])
    return f"{base}.{name}" if name else base


def _has_verified_provenance(transaction: _VerifiedTransaction) -> bool:
    frame = inspect.currentframe()
    try:
        frame = frame.f_back if frame is not None else None
        while frame is not None:
            if (
                frame.f_globals.get("__verified_transaction__") is transaction
                or frame.f_globals.get("__builtins__") is transaction.builtins
            ):
                return True
            frame = frame.f_back
    finally:
        del frame
    return False


def _finish_transaction(transaction: _VerifiedTransaction) -> None:
    if _TRANSACTIONS.get(transaction.package_name) is not transaction:
        return
    transaction.active = False
    _clear_transaction(transaction.package_name, transaction)


def _validate_stdlib_preloads() -> None:
    for name, module in tuple(sys.modules.items()):
        if name.partition(".")[0] not in _STDLIB_NAMES:
            continue
        baseline = _TRUSTED_STDLIB_BASELINE.get(name)
        if baseline is not None and baseline is not module:
            raise PackageTrustError("stdlib module preload is untrusted")


def _non_stdlib_import(fullname: str) -> bool:
    root = fullname.partition(".")[0]
    return root not in _STDLIB_NAMES


def discard_verified_package(package_name: str) -> None:
    """Drop one verifier transaction after an unsupported export is found."""

    with _TRANSACTION_LOCK:
        _discard_namespace(package_name)
        _clear_transaction(package_name)


__all__ = [
    "MAX_IDENTITY_FILE_BYTES",
    "MAX_PACKAGE_AGGREGATE_BYTES",
    "MAX_PACKAGE_FILE_COUNT",
    "MAX_SERIALIZED_IDENTITY_BYTES",
    "ExpectedPackageFile",
    "PackageIdentity",
    "PackageTrustBinding",
    "PackageTrustError",
    "VerifiedFile",
    "deserialize_identity",
    "discard_verified_package",
    "identity_matches",
    "load_verified_package",
    "read_verified_bytes",
    "reject_preloaded_namespace",
    "serialize_identity",
    "serialized_identity_size",
    "use_verified_package",
    "validate_distribution",
]
