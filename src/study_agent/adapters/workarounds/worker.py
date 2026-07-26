"""Short-lived PDF parser worker.

This module deliberately imports no optional parser at module import time.  The
child applies resource limits before importing :mod:`pypdf`; the parent treats
any containment or worker protocol failure as an attempted failure.
"""

from __future__ import annotations

import importlib
import multiprocessing
import os
from collections.abc import Callable, Sequence
from multiprocessing.connection import Connection
from typing import Any, Final, Protocol, cast

from .renderer import MAX_PDF_MARKDOWN_OUTPUT_BYTES, canonical_pdf_markdown

MAX_WORKER_CPU_SECONDS: Final = 3
MAX_WORKER_ADDRESS_SPACE_BYTES: Final = 256 * 1024 * 1024
MAX_WORKER_FILE_BYTES: Final = MAX_PDF_MARKDOWN_OUTPUT_BYTES
MAX_WORKER_DESCRIPTORS: Final = 32


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


_PdfReaderFactory = Callable[..., _PdfReader]


def containment_supported() -> bool:
    """Return whether the reference POSIX resource contract is available."""

    if os.name != "posix":
        return False
    try:
        import resource

        return all(
            hasattr(resource, name)
            for name in ("RLIMIT_CPU", "RLIMIT_AS", "RLIMIT_FSIZE", "RLIMIT_NOFILE")
        )
    except ImportError:
        return False


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


def _worker_entry(input_bytes: bytes, sender: Connection[Any]) -> None:
    """Parse one byte buffer and send either canonical bytes or a short code."""

    try:
        # This must remain before the optional import below.
        apply_resource_limits()
        import io

        pypdf_module = importlib.import_module("pypdf")
        reader_factory = cast(_PdfReaderFactory, pypdf_module.PdfReader)
        reader = reader_factory(io.BytesIO(input_bytes), strict=True)
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
        sender.send((True, output))
    except PdfWorkerError as error:
        try:
            sender.send((False, error.code))
        except (BrokenPipeError, EOFError, OSError):
            return
    except Exception:
        # Do not expose parser internals or unbounded exception text over IPC.
        try:
            sender.send((False, "malformed_or_unsupported_pdf"))
        except (BrokenPipeError, EOFError, OSError):
            return
    finally:
        sender.close()


def parse_in_worker(input_bytes: bytes, timeout_seconds: float) -> bytes:
    """Parse bytes in a fresh contained process, with terminate/kill cleanup."""

    if not isinstance(input_bytes, bytes):
        raise PdfWorkerError("invalid_worker_input")
    if timeout_seconds <= 0 or not containment_supported():
        raise PdfWorkerError("resource_containment_unavailable")
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_worker_entry, args=(input_bytes, child))
    try:
        process.start()
    except (OSError, RuntimeError):
        parent.close()
        child.close()
        raise PdfWorkerError("worker_spawn_failed") from None
    child.close()
    try:
        if not parent.poll(timeout_seconds):
            process.terminate()
            process.join(0.25)
            if process.is_alive():
                process.kill()
                process.join(0.25)
            raise PdfWorkerError("worker_timeout")
        try:
            response = parent.recv()
        except (EOFError, OSError):
            raise PdfWorkerError("worker_protocol_failed") from None
        if (
            not isinstance(response, tuple)
            or len(response) != 2
            or type(response[0]) is not bool
        ):
            raise PdfWorkerError("worker_protocol_failed")
        success, payload = response
        if not success:
            if not isinstance(payload, str) or len(payload) > 128:
                raise PdfWorkerError("worker_protocol_failed")
            raise PdfWorkerError(payload)
        if not isinstance(payload, bytes) or len(payload) > MAX_PDF_MARKDOWN_OUTPUT_BYTES:
            raise PdfWorkerError("output_limit_exceeded")
        return payload
    finally:
        if process.is_alive():
            process.terminate()
        process.join(0.25)
        if process.is_alive():
            process.kill()
            process.join(0.25)
        parent.close()


__all__ = [
    "MAX_WORKER_ADDRESS_SPACE_BYTES",
    "MAX_WORKER_CPU_SECONDS",
    "MAX_WORKER_DESCRIPTORS",
    "MAX_WORKER_FILE_BYTES",
    "PdfWorkerError",
    "apply_resource_limits",
    "containment_supported",
    "parse_in_worker",
]
