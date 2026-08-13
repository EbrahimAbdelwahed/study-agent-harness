"""Short-lived PDF parser worker.

The parser is optional executable input.  The child therefore receives a
strictly framed byte request, returns a strictly framed byte response, and is
started in a fresh process group with a descriptor-bound interpreter.  No
executable deserialization crosses the process seam.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import select
import signal
import struct
import sys
import sysconfig
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any, Final, Protocol, cast

from study_agent.adapters.package_trust import (
    MAX_IDENTITY_FILE_BYTES,
    MAX_SERIALIZED_IDENTITY_BYTES,
    PackageIdentity,
    PackageTrustBinding,
    PackageTrustError,
    deserialize_identity,
    discard_verified_package,
    identity_matches,
    reject_preloaded_namespace,
    serialize_identity,
    serialized_identity_size,
    use_verified_package,
    validate_distribution,
)

from .renderer import MAX_PDF_MARKDOWN_OUTPUT_BYTES, canonical_pdf_markdown

MAX_WORKER_CPU_SECONDS: Final = 3
MAX_WORKER_ADDRESS_SPACE_BYTES: Final = 256 * 1024 * 1024
MAX_WORKER_FILE_BYTES: Final = MAX_PDF_MARKDOWN_OUTPUT_BYTES
MAX_WORKER_DESCRIPTORS: Final = 32
MAX_WORKER_INPUT_BYTES: Final = 16 * 1024 * 1024
_MAX_WORKER_IPC_BYTES: Final = MAX_PDF_MARKDOWN_OUTPUT_BYTES + 1024
_MAX_WORKER_ERROR_BYTES: Final = 128
_PROTOCOL_MAGIC: Final = b"SAW1"
_PROTOCOL_VERSION: Final = 1
_REQUEST_HEADER = struct.Struct("!4sBII")
_RESPONSE_HEADER = struct.Struct("!4sBBI")
_REAP_GRACE_SECONDS: Final = 0.25
_PROCESS_CLEANUP_SECONDS: Final = 0.5
_MISSING_WAIT_STATUS: Final = -1
_WORKER_ERROR_CODES: Final = frozenset(
    {
        "encrypted_pdf",
        "malformed_or_unsupported_pdf",
        "output_limit_exceeded",
        "page_limit_exceeded",
        "parser_identity_oversized",
        "parser_import_path_unavailable",
        "pdf_parser_installation_changed",
        "pdf_parser_installation_untrusted",
        "pdf_parser_unavailable",
        "pdf_parser_version_unavailable",
        "resource_containment_unavailable",
        "worker_bootstrap_changed",
        "worker_bootstrap_unavailable",
        "worker_bootstrap_untrusted",
        "worker_interpreter_changed",
        "worker_interpreter_oversized",
        "worker_interpreter_unavailable",
        "worker_protocol_failed",
        "worker_request_write_failed",
        "worker_spawn_failed",
        "worker_timeout",
        "worker_input_oversized",
        "invalid_worker_input",
    }
)


def _initial_file_identity(path: Path) -> tuple[int, int, int, int, int] | None:
    try:
        metadata = path.stat()
        if (metadata.st_mode & 0o170000) != 0o100000 or metadata.st_nlink != 1:
            return None
        return (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_nlink,
        )
    except OSError:
        return None


def _capture_file_digest(path: Path) -> str | None:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return None
    try:
        metadata = os.fstat(descriptor)
        if (
            (metadata.st_mode & 0o170000) != 0o100000
            or metadata.st_nlink != 1
            or metadata.st_size > MAX_IDENTITY_FILE_BYTES
        ):
            return None
        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
        if (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_nlink,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_nlink,
        ):
            return None
        return digest.hexdigest()
    except OSError:
        return None
    finally:
        with suppress(OSError):
            os.close(descriptor)


try:
    _TRUSTED_INTERPRETER_PATH: Path = Path(sys.executable).resolve(strict=True)
    _TRUSTED_INTERPRETER_IDENTITY = _initial_file_identity(_TRUSTED_INTERPRETER_PATH)
    _TRUSTED_WORKER_PATH: Path = Path(__file__).resolve(strict=True)
    _TRUSTED_WORKER_IDENTITY = _initial_file_identity(_TRUSTED_WORKER_PATH)
    _TRUSTED_INTERPRETER_DIGEST = _capture_file_digest(_TRUSTED_INTERPRETER_PATH)
    _TRUSTED_WORKER_DIGEST = _capture_file_digest(_TRUSTED_WORKER_PATH)
    _TRUSTED_HARNESS_ROOT = _TRUSTED_WORKER_PATH.parents[3]
except (OSError, RuntimeError, TypeError, ValueError):
    _TRUSTED_INTERPRETER_PATH = Path("/")
    _TRUSTED_INTERPRETER_IDENTITY = None
    _TRUSTED_WORKER_PATH = Path("/")
    _TRUSTED_WORKER_IDENTITY = None
    _TRUSTED_INTERPRETER_DIGEST = None
    _TRUSTED_WORKER_DIGEST = None
    _TRUSTED_HARNESS_ROOT = Path("/")

_TRUSTED_BOOTSTRAP_RELATIVE: tuple[str, ...] = (
    "study_agent/__init__.py",
    "study_agent/adapters/__init__.py",
    "study_agent/adapters/package_trust.py",
    "study_agent/adapters/workarounds/__init__.py",
    "study_agent/adapters/workarounds/manifest.py",
    "study_agent/adapters/workarounds/pdf_markdown.py",
    "study_agent/adapters/workarounds/renderer.py",
    "study_agent/adapters/workarounds/worker.py",
)
_TRUSTED_BOOTSTRAP_MANIFEST: tuple[tuple[str, str], ...] = tuple(
    (
        relative,
        digest,
    )
    for relative in _TRUSTED_BOOTSTRAP_RELATIVE
    if (digest := _capture_file_digest(_TRUSTED_HARNESS_ROOT / relative)) is not None
)


class PdfWorkerError(RuntimeError):
    """A parser worker could not produce a bounded result."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _PdfPage(Protocol):
    def extract_text(self) -> str | None: ...


class _PdfReader(Protocol):
    is_encrypted: bool
    pages: Sequence[_PdfPage]


class _ByteSender(Protocol):
    def send(self, value: bytes) -> None: ...


_PdfReaderFactory = Callable[..., _PdfReader]
_ParserIdentity = PackageIdentity


def containment_supported() -> bool:
    """Return whether the verified Linux resource contract is available."""

    if os.name != "posix" or not sys.platform.startswith("linux"):
        return False
    try:
        import resource

        return all(
            hasattr(resource, name)
            for name in ("RLIMIT_CPU", "RLIMIT_AS", "RLIMIT_FSIZE", "RLIMIT_NOFILE")
        ) and hasattr(os, "posix_spawn")
    except ImportError:
        return False


def _verified_pypdf_binding(
    package_trust: PackageTrustBinding | None = None,
) -> _ParserIdentity:
    """Bind pypdf to an approved root and immutable file identities."""

    if package_trust is None:
        raise PdfWorkerError("pdf_parser_installation_untrusted")
    if package_trust.package_name != "pypdf" or package_trust.expected_version != "6.14.2":
        raise PdfWorkerError("pdf_parser_version_unavailable")
    try:
        reject_preloaded_namespace("pypdf")
        return validate_distribution(package_trust)
    except PackageTrustError as error:
        if str(error) in {
            "optional package identity changed",
            "approved package root changed",
            "optional package file changed",
        }:
            raise PdfWorkerError("pdf_parser_installation_changed") from None
        raise PdfWorkerError("pdf_parser_installation_untrusted") from None
    except Exception:
        raise PdfWorkerError("pdf_parser_unavailable") from None


def _verified_pypdf_import_root(
    package_trust: PackageTrustBinding | None = None,
) -> Path:
    """Return the approved parser root for preflight compatibility callers."""

    identity = _verified_pypdf_binding(package_trust)
    try:
        def validate_export(module: object) -> Path:
            if not callable(getattr(module, "PdfReader", None)):
                raise PackageTrustError("pypdf supported API is unavailable")
            return identity.binding.approved_root

        return cast(Path, use_verified_package(identity, validate_export))
    except PackageTrustError:
        discard_verified_package("pypdf")
        raise PdfWorkerError("pdf_parser_installation_untrusted") from None


def _identity_matches(identity: _ParserIdentity) -> bool:
    return identity_matches(identity)


def _parser_spec_matches(identity: _ParserIdentity) -> bool:
    """Check the host-bound parser layout without calling find_spec hooks."""

    try:
        reject_preloaded_namespace(identity.binding.package_name)
        return (
            identity.package_origin
            == identity.binding.approved_root / identity.binding.package_name / "__init__.py"
            and identity.package_root
            == identity.binding.approved_root / identity.binding.package_name
        )
    except (PackageTrustError, OSError, RuntimeError, TypeError, ValueError):
        return False


def _revalidate_parser_identity(identity: _ParserIdentity) -> bool:
    return _identity_matches(identity) and _parser_spec_matches(identity)


def _set_limit(resource_module: Any, name: str, target: int) -> None:
    """Set one soft limit without raising a hard limit on the host."""

    constant = getattr(resource_module, name)
    _, current_hard = resource_module.getrlimit(constant)
    hard = target if current_hard == resource_module.RLIM_INFINITY else min(current_hard, target)
    if hard <= 0:
        raise PdfWorkerError("resource_containment_unavailable")
    resource_module.setrlimit(constant, (min(target, hard), hard))


def apply_resource_limits() -> None:
    """Apply CPU, address-space, file-size, and descriptor limits."""

    if not containment_supported():
        raise PdfWorkerError("resource_containment_unavailable")
    try:
        import resource

        _set_limit(resource, "RLIMIT_CPU", MAX_WORKER_CPU_SECONDS)
        _set_limit(resource, "RLIMIT_AS", MAX_WORKER_ADDRESS_SPACE_BYTES)
        _set_limit(resource, "RLIMIT_FSIZE", MAX_WORKER_FILE_BYTES)
        _set_limit(resource, "RLIMIT_NOFILE", MAX_WORKER_DESCRIPTORS)
    except PdfWorkerError:
        raise
    except (ImportError, OSError, ValueError):
        raise PdfWorkerError("resource_containment_unavailable") from None


def _sanitized_import_path(parser_import_root: str) -> list[str]:
    try:
        root = Path(parser_import_root).resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise PdfWorkerError("parser_import_path_unavailable") from None
    if not root.is_dir():
        raise PdfWorkerError("parser_import_path_unavailable")
    paths = [str(root)]
    configured = sysconfig.get_paths()
    for key in ("stdlib", "platstdlib"):
        value = configured.get(key)
        if not isinstance(value, str):
            continue
        try:
            candidate = Path(value).resolve(strict=True)
        except (OSError, RuntimeError, TypeError, ValueError):
            continue
        if candidate.is_dir() and str(candidate) not in paths:
            paths.append(str(candidate))
    return paths


def _worker_entry(
    input_bytes: bytes, sender: _ByteSender, parser_identity: _ParserIdentity
) -> None:
    """Compatibility entry for harness callers using a byte-only sender."""

    try:
        # This must remain before the optional import below.
        apply_resource_limits()
        if not _revalidate_parser_identity(parser_identity):
            raise PdfWorkerError("pdf_parser_installation_changed")
        sys.path = _sanitized_import_path(str(parser_identity.binding.approved_root))
        sys.path_importer_cache.clear()
        os.environ.clear()
        if not _revalidate_parser_identity(parser_identity):
            raise PdfWorkerError("pdf_parser_installation_changed")
        # Keep the compatibility import point inside the verified transaction;
        # the transaction-local finder supplies fresh bytes for this import.
        use_verified_package(parser_identity, lambda _module: importlib.import_module("pypdf"))
        sender.send(_encode_response(True, _parse_verified_document(input_bytes, parser_identity)))
    except PdfWorkerError as error:
        try:
            sender.send(_encode_response(False, error.code))
        except (BrokenPipeError, EOFError, OSError):
            return
    except Exception:
        try:
            sender.send(_encode_response(False, "malformed_or_unsupported_pdf"))
        except (BrokenPipeError, EOFError, OSError):
            return


def _parse_verified_document(input_bytes: bytes, parser_identity: _ParserIdentity) -> bytes:
    """Parse only after the caller has fixed the path and verified identity."""

    import io

    def parse(module: object) -> bytes:
        if not _parser_spec_matches(parser_identity) or not _identity_matches(parser_identity):
            raise PdfWorkerError("pdf_parser_installation_changed")
        reader_factory = getattr(module, "PdfReader", None)
        if not callable(reader_factory):
            raise PdfWorkerError("pdf_parser_unavailable")
        reader = cast(_PdfReaderFactory, reader_factory)(io.BytesIO(input_bytes), strict=True)
        if reader.is_encrypted:
            raise PdfWorkerError("encrypted_pdf")
        page_count = len(reader.pages)
        if page_count > 256:
            raise PdfWorkerError("page_limit_exceeded")
        page_texts: list[str] = []
        for page in reader.pages:
            extracted = page.extract_text()
            page_texts.append(extracted if isinstance(extracted, str) else "")
        output = canonical_pdf_markdown(page_texts)
        if len(output) > MAX_PDF_MARKDOWN_OUTPUT_BYTES:
            raise PdfWorkerError("output_limit_exceeded")
        return output

    try:
        return cast(bytes, use_verified_package(parser_identity, parse))
    except PackageTrustError as error:
        if str(error) == "optional package identity changed":
            raise PdfWorkerError("pdf_parser_installation_changed") from None
        raise


def _subprocess_parse(
    input_bytes: bytes,
    parser_identity: _ParserIdentity,
    harness_root: str,
) -> bytes:
    """Entry called after the fixed child bootstrap has set its paths."""

    apply_resource_limits()
    sys.path = _sanitized_import_path(str(parser_identity.binding.approved_root))[1:]
    sys.path_importer_cache.clear()
    os.environ.clear()
    if not _revalidate_parser_identity(parser_identity):
        raise PdfWorkerError("pdf_parser_installation_changed")
    return _parse_verified_document(input_bytes, parser_identity)


_SUBPROCESS_BOOTSTRAP = r'''
import hashlib
import importlib.util
import json
import os
import resource
import struct
import sys
import sysconfig
import types

MAGIC = b"SAW1"
VERSION = 1
REQUEST = struct.Struct("!4sBII")
RESPONSE = struct.Struct("!4sBBI")
MAX_IDENTITY = 2 * 1024 * 1024
MAX_INPUT = 16 * 1024 * 1024
MAX_OUTPUT = 4 * 1024 * 1024
MAX_ERROR = 128

harness_root, parser_root, bootstrap_manifest_wire = sys.argv[1:4]

os.chdir("/")

for name, target in (
    ("RLIMIT_CPU", 3),
    ("RLIMIT_AS", 256 * 1024 * 1024),
    ("RLIMIT_FSIZE", 64 * 1024 * 1024),
    ("RLIMIT_NOFILE", 32),
):
    constant = getattr(resource, name)
    _, current_hard = resource.getrlimit(constant)
    hard = target if current_hard == resource.RLIM_INFINITY else min(current_hard, target)
    if hard <= 0:
        raise RuntimeError("resource containment unavailable")
    resource.setrlimit(constant, (min(target, hard), hard))

configured = sysconfig.get_paths()
paths = []
for key in ("stdlib", "platstdlib"):
    value = configured.get(key)
    if isinstance(value, str) and value not in paths:
        paths.append(value)
sys.path = paths
os.environ.clear()

def read_exact(stream, size):
    chunks = bytearray()
    while len(chunks) < size:
        chunk = stream.read(size - len(chunks))
        if not chunk:
            raise RuntimeError("truncated worker request")
        chunks.extend(chunk)
    return bytes(chunks)

def write_all(stream, payload):
    view = memoryview(payload)
    while view:
        written = stream.write(view)
        if not written:
            raise RuntimeError("worker response write failed")
        view = view[written:]
    stream.flush()

def read_verified_source(path, expected):
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if (
            (metadata.st_mode & 0o170000) != 0o100000
            or metadata.st_nlink != 1
            or metadata.st_size > 64 * 1024 * 1024
        ):
            raise RuntimeError("worker bootstrap identity unavailable")
        data = bytearray()
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            data.extend(chunk)
        after = os.fstat(descriptor)
        if (
            (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        ):
            raise RuntimeError("worker bootstrap changed")
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError("worker bootstrap changed")
        return bytes(data)
    finally:
        os.close(descriptor)

try:
    bootstrap_manifest = json.loads(bootstrap_manifest_wire)
    if not isinstance(bootstrap_manifest, list) or not bootstrap_manifest:
        raise ValueError
    root = os.path.realpath(harness_root)
    if root != harness_root:
        raise ValueError
    for item in bootstrap_manifest:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not isinstance(item[0], str)
            or not isinstance(item[1], str)
            or not item[0]
            or "\\" in item[0]
            or item[0].startswith("/")
            or any(part in ("", ".", "..") for part in item[0].split("/"))
            or len(item[1]) != 64
            or any(value not in "0123456789abcdef" for value in item[1])
        ):
            raise ValueError
        path = os.path.join(harness_root, *item[0].split("/"))
        if os.path.realpath(path) != path or not os.path.realpath(path).startswith(root + os.sep):
            raise ValueError
        item.append(read_verified_source(path, item[1]))
except (TypeError, ValueError, RuntimeError, OSError):
    raise RuntimeError("worker bootstrap changed") from None

verified_sources = {}
for relative, digest, source in bootstrap_manifest:
    module_name = relative[:-3].replace("/", ".")
    is_package = module_name.endswith(".__init__")
    if is_package:
        module_name = module_name[:-len(".__init__")]
    verified_sources[module_name] = (source, is_package)

class BootstrapLoader:
    def __init__(self, name, source, is_package):
        self.name = name
        self.source = source
        self.is_package = is_package

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = "<verified:" + self.name + ">"
        if self.is_package:
            module.__path__ = []
        exec(compile(self.source, module.__file__, "exec"), module.__dict__)

class BootstrapFinder:
    def find_spec(self, fullname, path=None, target=None):
        value = verified_sources.get(fullname)
        if value is None:
            return None
        source, is_package = value
        return importlib.util.spec_from_loader(
            fullname,
            BootstrapLoader(fullname, source, is_package),
            is_package=is_package,
        )

sys.meta_path.insert(0, BootstrapFinder())
workarounds = types.ModuleType("study_agent.adapters.workarounds")
workarounds.__path__ = []
workarounds.__package__ = "study_agent.adapters"
sys.modules["study_agent.adapters.workarounds"] = workarounds
worker = importlib.import_module("study_agent.adapters.workarounds.worker")

try:
    header = read_exact(sys.stdin.buffer, REQUEST.size)
    magic, version, identity_size, input_size = REQUEST.unpack(header)
    if (
        magic != MAGIC
        or version != VERSION
        or identity_size > MAX_IDENTITY
        or input_size > MAX_INPUT
    ):
        raise RuntimeError("worker request is invalid")
    identity_bytes = read_exact(sys.stdin.buffer, identity_size)
    input_bytes = read_exact(sys.stdin.buffer, input_size)
    if sys.stdin.buffer.read(1):
        raise RuntimeError("worker request has trailing bytes")
    identity = worker.deserialize_identity(identity_bytes)
    output = worker._subprocess_parse(input_bytes, identity, harness_root)
    response = RESPONSE.pack(MAGIC, VERSION, 0, len(output)) + output
except worker.PdfWorkerError as error:
    code = error.code.encode("ascii")
    if len(code) > MAX_ERROR or not code or not all(
        97 <= value <= 122 or value == 95 for value in code
    ):
        code = b"worker_protocol_failed"
    response = RESPONSE.pack(MAGIC, VERSION, 1, len(code)) + code
except Exception:
    code = b"malformed_or_unsupported_pdf"
    response = RESPONSE.pack(MAGIC, VERSION, 1, len(code)) + code
write_all(sys.stdout.buffer, response)
'''
_TRUSTED_BOOTSTRAP_DIGEST = hashlib.sha256(_SUBPROCESS_BOOTSTRAP.encode("utf-8")).hexdigest()


class _WorkerProtocolError(RuntimeError):
    pass


def _encode_response(success: bool, payload: bytes | str) -> bytes:
    if success:
        if not isinstance(payload, bytes) or len(payload) > MAX_PDF_MARKDOWN_OUTPUT_BYTES:
            raise _WorkerProtocolError("worker response is oversized")
        status = 0
    else:
        if not isinstance(payload, str):
            raise _WorkerProtocolError("worker response is invalid")
        payload = payload.encode("ascii")
        if not payload or len(payload) > _MAX_WORKER_ERROR_BYTES or not all(
            value == 95 or 97 <= value <= 122 for value in payload
        ):
            raise _WorkerProtocolError("worker response is invalid")
        status = 1
    return _RESPONSE_HEADER.pack(_PROTOCOL_MAGIC, _PROTOCOL_VERSION, status, len(payload)) + payload


def _encode_request(input_bytes: bytes, identity: _ParserIdentity) -> bytes:
    identity_bytes = serialize_identity(identity)
    if len(input_bytes) > MAX_WORKER_INPUT_BYTES:
        raise PdfWorkerError("worker_input_oversized")
    if len(identity_bytes) > MAX_SERIALIZED_IDENTITY_BYTES:
        raise PdfWorkerError("parser_identity_oversized")
    return (
        _REQUEST_HEADER.pack(
            _PROTOCOL_MAGIC,
            _PROTOCOL_VERSION,
            len(identity_bytes),
            len(input_bytes),
        )
        + identity_bytes
        + input_bytes
    )


def _remaining(deadline: float) -> float:
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError
    return value


def _write_fd(fd: int, payload: bytes, deadline: float) -> None:
    view = memoryview(payload)
    while view:
        _, writable, _ = select.select([], [fd], [], _remaining(deadline))
        if not writable:
            raise TimeoutError
        try:
            written = os.write(fd, view)
        except BlockingIOError:
            continue
        if written <= 0:
            raise _WorkerProtocolError("worker request write failed")
        view = view[written:]


def _read_fd(fd: int, size: int, deadline: float) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        ready, _, _ = select.select([fd], [], [], _remaining(deadline))
        if not ready:
            raise TimeoutError
        try:
            chunk = os.read(fd, size - len(chunks))
        except BlockingIOError:
            continue
        if not chunk:
            raise _WorkerProtocolError("worker response is truncated")
        chunks.extend(chunk)
    return bytes(chunks)


def _read_response(fd: int, deadline: float) -> tuple[bool, bytes]:
    header = _read_fd(fd, _RESPONSE_HEADER.size, deadline)
    magic, version, status, payload_size = _RESPONSE_HEADER.unpack(header)
    if magic != _PROTOCOL_MAGIC or version != _PROTOCOL_VERSION or status not in (0, 1):
        raise _WorkerProtocolError("worker response header is invalid")
    limit = MAX_PDF_MARKDOWN_OUTPUT_BYTES if status == 0 else _MAX_WORKER_ERROR_BYTES
    if payload_size > limit:
        raise _WorkerProtocolError("worker response is oversized")
    return status == 0, _read_fd(fd, payload_size, deadline)


def _wait_pid_status(pid: int, deadline: float) -> int | None:
    while True:
        try:
            waited, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return _MISSING_WAIT_STATUS
        if waited == pid:
            return status
        try:
            _remaining(deadline)
        except TimeoutError:
            return None
        select.select([], [], [], min(0.01, deadline - time.monotonic()))


def _wait_pid(pid: int, deadline: float) -> bool:
    return _wait_pid_status(pid, deadline) is not None


def _ensure_eof(fd: int, deadline: float) -> None:
    ready, _, _ = select.select([fd], [], [], _remaining(deadline))
    if not ready:
        raise _WorkerProtocolError("worker response did not reach EOF")
    try:
        extra = os.read(fd, 1)
    except BlockingIOError:
        raise _WorkerProtocolError("worker response did not reach EOF") from None
    if extra:
        raise _WorkerProtocolError("worker response has trailing bytes")


def _terminate_group(pid: int, deadline: float) -> None:
    term_deadline = max(time.monotonic(), deadline - _REAP_GRACE_SECONDS)
    with suppress(OSError, ProcessLookupError):
        os.killpg(pid, signal.SIGTERM)
    with suppress(OSError, ProcessLookupError):
        os.kill(pid, signal.SIGTERM)
    _wait_pid(pid, term_deadline)
    with suppress(OSError, ProcessLookupError):
        os.killpg(pid, signal.SIGKILL)
    with suppress(OSError, ProcessLookupError):
        os.kill(pid, signal.SIGKILL)
    _wait_pid(pid, deadline)


def _close_fd(fd: int | None) -> None:
    if fd is not None:
        with suppress(OSError):
            os.close(fd)


def _read_file_digest(path: Path, expected_digest: str | None = None) -> str:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise PdfWorkerError("worker_bootstrap_unavailable") from None
    try:
        metadata = os.fstat(descriptor)
        if not stat_is_regular_single_link(metadata) or metadata.st_size > MAX_IDENTITY_FILE_BYTES:
            raise PdfWorkerError("worker_bootstrap_untrusted")
        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
        if (
            metadata.st_dev != after.st_dev
            or metadata.st_ino != after.st_ino
            or metadata.st_size != after.st_size
            or metadata.st_mtime_ns != after.st_mtime_ns
        ):
            raise PdfWorkerError("worker_bootstrap_changed")
        value = digest.hexdigest()
        if expected_digest is not None and value != expected_digest:
            raise PdfWorkerError("worker_bootstrap_changed")
        return value
    except OSError:
        raise PdfWorkerError("worker_bootstrap_unavailable") from None
    finally:
        _close_fd(descriptor)


def _open_interpreter() -> tuple[int, str]:
    descriptor: int | None = None
    try:
        executable = _TRUSTED_INTERPRETER_PATH
        if (
            _TRUSTED_INTERPRETER_IDENTITY is None
            or _initial_file_identity(executable) != _TRUSTED_INTERPRETER_IDENTITY
        ):
            raise PdfWorkerError("worker_interpreter_changed")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(executable, flags)
        metadata = os.fstat(descriptor)
        if (
            not stat_is_regular_single_link(metadata)
            or (
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_size,
                metadata.st_mtime_ns,
                metadata.st_nlink,
            )
            != _TRUSTED_INTERPRETER_IDENTITY
        ):
            os.close(descriptor)
            descriptor = None
            raise PdfWorkerError("worker_interpreter_changed")
        digest = _read_descriptor_digest(descriptor, metadata)
        if _TRUSTED_INTERPRETER_DIGEST is None or digest != _TRUSTED_INTERPRETER_DIGEST:
            os.close(descriptor)
            descriptor = None
            raise PdfWorkerError("worker_interpreter_changed")
        proc_path = f"/proc/self/fd/{descriptor}"
        if not os.path.exists(proc_path):
            os.close(descriptor)
            descriptor = None
            raise PdfWorkerError("worker_interpreter_unavailable")
        assert descriptor is not None
        return descriptor, proc_path
    except PdfWorkerError:
        if descriptor is not None:
            _close_fd(descriptor)
        raise
    except (OSError, RuntimeError, ValueError):
        if descriptor is not None:
            _close_fd(descriptor)
        raise PdfWorkerError("worker_interpreter_unavailable") from None


def stat_is_regular_single_link(metadata: os.stat_result) -> bool:
    return stat_mode_is_regular(metadata.st_mode) and metadata.st_nlink == 1


def stat_mode_is_regular(mode: int) -> bool:
    return (mode & 0o170000) == 0o100000


def _read_descriptor_digest(
    descriptor: int, metadata: os.stat_result, expected_digest: str | None = None
) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = os.read(descriptor, 64 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        if metadata.st_size > MAX_IDENTITY_FILE_BYTES:
            raise PdfWorkerError("worker_interpreter_oversized")
    after = os.fstat(descriptor)
    if (
        metadata.st_dev != after.st_dev
        or metadata.st_ino != after.st_ino
        or metadata.st_size != after.st_size
        or metadata.st_mtime_ns != after.st_mtime_ns
    ):
        raise PdfWorkerError("worker_interpreter_changed")
    value = digest.hexdigest()
    if expected_digest is not None and value != expected_digest:
        raise PdfWorkerError("worker_interpreter_changed")
    return value


def parse_in_worker(
    input_bytes: bytes,
    timeout_seconds: float,
    *,
    package_trust: PackageTrustBinding | None = None,
) -> bytes:
    """Parse bytes in a fresh contained process with bounded cleanup."""

    input_read: int | None = None
    input_write: int | None = None
    output_read: int | None = None
    output_write: int | None = None
    devnull: int | None = None
    interpreter_fd: int | None = None
    pid: int | None = None
    if not isinstance(input_bytes, bytes):
        raise PdfWorkerError("invalid_worker_input")
    if len(input_bytes) > MAX_WORKER_INPUT_BYTES:
        raise PdfWorkerError("worker_input_oversized")
    if timeout_seconds <= 0 or not containment_supported():
        raise PdfWorkerError("resource_containment_unavailable")
    try:
        parser_identity = _verified_pypdf_binding(package_trust)
        if not _revalidate_parser_identity(parser_identity):
            raise PdfWorkerError("pdf_parser_installation_changed")
        if serialized_identity_size(parser_identity) > MAX_SERIALIZED_IDENTITY_BYTES:
            raise PdfWorkerError("parser_identity_oversized")
        if (
            _TRUSTED_WORKER_IDENTITY is None
            or _TRUSTED_WORKER_DIGEST is None
            or _initial_file_identity(_TRUSTED_WORKER_PATH) != _TRUSTED_WORKER_IDENTITY
        ):
            raise PdfWorkerError("worker_bootstrap_changed")
        if len(_TRUSTED_BOOTSTRAP_MANIFEST) != len(_TRUSTED_BOOTSTRAP_RELATIVE):
            raise PdfWorkerError("worker_bootstrap_unavailable")
        if (
            hashlib.sha256(_SUBPROCESS_BOOTSTRAP.encode("utf-8")).hexdigest()
            != _TRUSTED_BOOTSTRAP_DIGEST
        ):
            raise PdfWorkerError("worker_bootstrap_changed")
        harness_root = _TRUSTED_HARNESS_ROOT
        _read_file_digest(_TRUSTED_WORKER_PATH, _TRUSTED_WORKER_DIGEST)
        bootstrap_manifest_wire = json.dumps(
            list(_TRUSTED_BOOTSTRAP_MANIFEST), separators=(",", ":")
        )
        request = _encode_request(input_bytes, parser_identity)
        interpreter_fd, interpreter_path = _open_interpreter()
        deadline = time.monotonic() + timeout_seconds
        input_read, input_write = os.pipe()
        output_read, output_write = os.pipe()
        devnull = os.open(os.devnull, os.O_WRONLY)
        for fd in (input_write, output_read):
            os.set_inheritable(fd, False)
        file_actions = [
            (os.POSIX_SPAWN_DUP2, input_read, 0),
            (os.POSIX_SPAWN_DUP2, output_write, 1),
            (os.POSIX_SPAWN_DUP2, devnull, 2),
            (os.POSIX_SPAWN_CLOSE, input_write),
            (os.POSIX_SPAWN_CLOSE, output_read),
        ]
        pid = os.posix_spawn(
            interpreter_path,
            [
                interpreter_path,
                "-I",
                "-S",
                "-c",
                _SUBPROCESS_BOOTSTRAP,
                str(harness_root),
                str(parser_identity.binding.approved_root),
                bootstrap_manifest_wire,
            ],
            {},
            file_actions=file_actions,
            setsid=True,
        )
        os.close(input_read)
        input_read = None
        os.close(output_write)
        output_write = None
        os.set_blocking(input_write, False)
        os.set_blocking(output_read, False)
        _write_fd(input_write, request, deadline)
        _close_fd(input_write)
        input_write = None
        success, payload = _read_response(output_read, deadline)
        status = _wait_pid_status(pid, deadline)
        if status is None:
            raise PdfWorkerError("worker_timeout")
        if status == _MISSING_WAIT_STATUS:
            raise _WorkerProtocolError("worker exit status is unavailable")
        try:
            exit_code = os.waitstatus_to_exitcode(status)
        except (OverflowError, ValueError):
            raise _WorkerProtocolError("worker exit status is invalid") from None
        if exit_code != 0:
            raise _WorkerProtocolError("worker exited unsuccessfully")
        _ensure_eof(output_read, min(deadline, time.monotonic() + _REAP_GRACE_SECONDS))
        if not success:
            try:
                code = payload.decode("ascii")
            except UnicodeDecodeError:
                raise _WorkerProtocolError("worker response code is invalid") from None
            if not code or len(code) > _MAX_WORKER_ERROR_BYTES or not all(
                character == "_" or "a" <= character <= "z" for character in code
            ) or code not in _WORKER_ERROR_CODES:
                raise _WorkerProtocolError("worker response code is invalid")
            raise PdfWorkerError(code)
        if len(payload) > MAX_PDF_MARKDOWN_OUTPUT_BYTES:
            raise PdfWorkerError("output_limit_exceeded")
        return payload
    except TimeoutError:
        raise PdfWorkerError("worker_timeout") from None
    except _WorkerProtocolError:
        raise PdfWorkerError("worker_protocol_failed") from None
    except PdfWorkerError:
        raise
    except (BrokenPipeError, OSError, TypeError, ValueError, RuntimeError):
        raise PdfWorkerError("worker_spawn_failed") from None
    finally:
        with suppress(BaseException):
            if pid is not None:
                cleanup_deadline = time.monotonic() + _PROCESS_CLEANUP_SECONDS
                _terminate_group(pid, cleanup_deadline)
        _close_fd(input_read)
        _close_fd(input_write)
        _close_fd(output_write)
        _close_fd(output_read)
        _close_fd(devnull)
        _close_fd(interpreter_fd)


__all__ = [
    "MAX_WORKER_ADDRESS_SPACE_BYTES",
    "MAX_WORKER_CPU_SECONDS",
    "MAX_WORKER_DESCRIPTORS",
    "MAX_WORKER_FILE_BYTES",
    "MAX_WORKER_INPUT_BYTES",
    "PdfWorkerError",
    "apply_resource_limits",
    "containment_supported",
    "deserialize_identity",
    "parse_in_worker",
]
