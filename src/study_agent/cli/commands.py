"""Host-authority command handlers for the reference CLI."""

from __future__ import annotations

import os
import signal
import stat
import threading
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from types import FrameType
from uuid import uuid4

from study_agent.adapters.filesystem import FilesystemExportWriter
from study_agent.application import ExportService
from study_agent.courses import course_profile_manifest
from study_agent.domain import (
    CorrelationId,
    CourseId,
    ExecutionContext,
    PrincipalKind,
    SessionId,
    SourceId,
)
from study_agent.domain._validation import JsonObject
from study_agent.domain.course import CourseProfile, SourcePolicy, TerminologyPolicy
from study_agent.domain.session import SessionStatus
from study_agent.ingestion.projection import source_manifest
from study_agent.sessions.events import grounded_answer_manifest

from .config import EMPTY_CONFIG, LocalRepositoryConfig
from .output import CommandOutcome
from .repository import (
    LocalRepository,
    ModelAdapterRegistry,
    initialize_local_repository,
)

_HOST_PRINCIPAL = "study-agent-cli"
_MAX_SOURCE_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class CommandRequest:
    repository: Path
    name: str
    values: dict[str, object]


async def execute(
    request: CommandRequest,
    *,
    model_adapters: ModelAdapterRegistry | None = None,
    environment: dict[str, str] | None = None,
) -> CommandOutcome:
    """Execute through the production composition root.

    Hosts may explicitly supply technical adapter registrations.  The CLI entry point
    deliberately supplies neither argument, so test or embedding adapters can never
    become an implicit production fallback.
    """
    if request.name == "init":
        return _init(request)
    with LocalRepository.open(
        request.repository,
        model_adapters=model_adapters,
        environment=environment,
    ) as repository:
        handlers = {
            "course.create": _course_create,
            "source.add": _source_add,
            "source.list": _source_list,
            "ask": _ask,
            "session.list": _session_list,
            "session.resume": _session_resume,
            "export": _export,
            "doctor": _doctor,
        }
        return await handlers[request.name](repository, request.values)


def _init(request: CommandRequest) -> CommandOutcome:
    config = request.values.get("config")
    if config is not None and not isinstance(config, LocalRepositoryConfig):
        raise ValueError("configuration is incompatible")
    paths = initialize_local_repository(request.repository, config or EMPTY_CONFIG)
    return CommandOutcome("init", {"repository": str(paths.root.absolute())})


async def _course_create(repository: LocalRepository, values: dict[str, object]) -> CommandOutcome:
    title = _text(values, "title")
    language = _text(values, "language")
    goals = _texts(values, "learning_goals")
    styles = _texts(values, "assessment_styles", required=False)
    raw_exam = values.get("exam_date")
    exam_date = None if raw_exam is None else date.fromisoformat(str(raw_exam))
    course_id = CourseId(
        str(values.get("course_id") or _derived_id("course", title, language, *goals))
    )
    profile = CourseProfile(
        course_id,
        title,
        language,
        exam_date,
        styles,
        goals,
        SourcePolicy(),
        TerminologyPolicy(),
    )
    created = repository.course_service.create(profile, _context(course_id))
    return CommandOutcome("course.create", course_profile_manifest(created))


async def _source_add(repository: LocalRepository, values: dict[str, object]) -> CommandOutcome:
    course_id = CourseId(_text(values, "course_id"))
    path, content = _read_source(repository.paths.root, _text(values, "path"))
    try:
        relative = path.relative_to(repository.paths.root.absolute())
    except ValueError as error:
        raise ValueError("source path must be inside the repository") from error
    source_id = SourceId(
        str(values.get("source_id") or _derived_id("source", relative.as_posix()))
    )
    course = repository.for_course(course_id)
    result = course.ingestion.ingest(
        filename=path.name,
        content=content,
        source_id=source_id,
        title=str(values.get("title") or path.stem),
        trust_level=_integer(values, "trust_level"),
        source_role=_text(values, "source_role"),
        context=_context(course_id),
    )
    canonical: JsonObject = {
        "status": result.status.value,
        "committed": True,
        "committed_sequence": result.committed_sequence,
        "source": source_manifest(result.source),
        "chunk_count": len(result.chunks),
    }
    try:
        receipt = repository.rebuild_retrieval()
    except Exception as error:
        raise SourceIndexError(canonical) from error
    return CommandOutcome(
        "source.add",
        {
            **canonical,
            "index": {
                "indexed_chunks": receipt.indexed_chunks,
                "index_version": receipt.index_version,
                "catalog_fingerprint": receipt.catalog_fingerprint,
            },
        },
    )


async def _source_list(repository: LocalRepository, values: dict[str, object]) -> CommandOutcome:
    course_id = CourseId(_text(values, "course_id"))
    repository.courses.get(course_id)
    records = repository.for_course(course_id).content.catalog()
    sources = tuple(
        {
            "source_id": str(item.source.source_id),
            "revision_id": str(item.source.revision_id),
            "title": item.source.title,
            "kind": item.source.kind.value,
            "source_role": item.source.source_role,
            "trust_level": item.source.trust_level,
            "is_current_revision": item.is_current_revision,
            "chunk_count": len(item.chunks),
        }
        for item in records
    )
    return CommandOutcome("source.list", {"course_id": str(course_id), "sources": sources})


async def _ask(repository: LocalRepository, values: dict[str, object]) -> CommandOutcome:
    course_id = CourseId(_text(values, "course_id"))
    repository.courses.get(course_id)
    session_value = values.get("session_id")
    session_id = SessionId(str(session_value or f"session-{uuid4()}"))
    key = str(values.get("idempotency_key") or f"ask-{uuid4()}")
    context = _context(
        course_id,
        session_id=session_id,
        idempotency_key=key,
        capabilities=frozenset({"study:ask"}),
    )
    receipt = repository.rebuild_retrieval()
    service = repository.grounding_service(
        course_id, repository.course_index_receipt(course_id, receipt)
    )
    if session_value is not None:
        session = repository.sessions.get_session(course_id, session_id)
        if session.status is not SessionStatus.ACTIVE:
            raise ValueError("ask requires an active session")
    if session_value is None:
        repository.session_service.start(context)
    result = await service.ask(_text(values, "question"), context)
    return CommandOutcome(
        "ask",
        {
            "course_id": str(course_id),
            "session_id": str(session_id),
            "answer_id": str(result.answer.id),
            "run_id": str(result.answer.run_id),
            "answer": grounded_answer_manifest(result.answer.answer),
        },
    )


async def _session_list(repository: LocalRepository, values: dict[str, object]) -> CommandOutcome:
    course_id = CourseId(_text(values, "course_id"))
    repository.courses.get(course_id)
    sessions = tuple(
        {
            "session_id": str(item.id),
            "status": item.status.value,
            "started_at": item.started_at.isoformat(),
            "interaction_count": len(item.interaction_ids),
            "answer_count": len(item.run_ids),
        }
        for item in repository.sessions.list_sessions(course_id)
    )
    return CommandOutcome("session.list", {"course_id": str(course_id), "sessions": sessions})


async def _session_resume(repository: LocalRepository, values: dict[str, object]) -> CommandOutcome:
    course_id = CourseId(_text(values, "course_id"))
    session_id = SessionId(_text(values, "session_id"))
    session = repository.session_service.resume(_context(course_id, session_id=session_id))
    return CommandOutcome(
        "session.resume",
        {
            "course_id": str(course_id),
            "session_id": str(session.id),
            "status": session.status.value,
        },
    )


async def _export(repository: LocalRepository, values: dict[str, object]) -> CommandOutcome:
    course_id = CourseId(_text(values, "course_id"))
    output = Path(_text(values, "output"))
    if not output.is_absolute():
        output = repository.paths.root / output
    bundle = ExportService(repository.events).assemble(course_id)
    receipt = FilesystemExportWriter().write(bundle, output)
    return CommandOutcome(
        "export",
        {
            "course_id": str(course_id),
            "destination": str(receipt.destination),
            "manifest_sha256": receipt.manifest_sha256,
            "high_water_sequence": receipt.high_water_sequence,
        },
    )


async def _doctor(repository: LocalRepository, values: dict[str, object]) -> CommandOutcome:
    del values
    courses = repository.course_catalog.list_courses()
    if not all(repository.events.verify_projection(profile.id) for profile in courses):
        raise RuntimeError("event replay does not match a persisted projection")
    repository.rebuild_retrieval()
    return CommandOutcome(
        "doctor",
        {
            "status": "ok",
            "schema_version": repository.config.schema_version,
            "course_count": len(courses),
            "sqlite_fts5": True,
            "event_replay": "ok",
            "retrieval_rebuild": "ok",
            "run_store": "ok",
        },
    )


class SourceIndexError(RuntimeError):
    """Canonical source committed but discardable retrieval rebuild failed."""

    def __init__(self, committed: JsonObject) -> None:
        self.committed = committed
        super().__init__("source committed, but retrieval index rebuild failed")


def _context(
    course_id: CourseId,
    *,
    session_id: SessionId | None = None,
    idempotency_key: str | None = None,
    capabilities: frozenset[str] = frozenset(),
) -> ExecutionContext:
    return ExecutionContext(
        PrincipalKind.HUMAN,
        _HOST_PRINCIPAL,
        course_id,
        CorrelationId(f"correlation-{uuid4()}"),
        capabilities,
        session_id,
        None,
        idempotency_key,
    )


def _derived_id(kind: str, *parts: str) -> str:
    digest = sha256("\0".join(parts).encode()).hexdigest()
    return f"{kind}-sha256:{digest}"


def _text(values: dict[str, object], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty trimmed text")
    return value


def _texts(values: dict[str, object], name: str, *, required: bool = True) -> tuple[str, ...]:
    value = values.get(name, ())
    if not isinstance(value, (tuple, list)) or any(
        not isinstance(item, str) or not item or item != item.strip() for item in value
    ):
        raise ValueError(f"{name} must contain trimmed text")
    result = tuple(value)
    if required and not result:
        raise ValueError(f"{name} must not be empty")
    return result


def _integer(values: dict[str, object], name: str) -> int:
    value = values.get(name)
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    return value


def _read_source(repository_root: Path, supplied: str) -> tuple[Path, bytes]:
    root = repository_root.resolve(strict=True)
    requested = Path(supplied).expanduser()
    lexical = requested if requested.is_absolute() else root / requested
    try:
        lexical_relative = lexical.relative_to(root)
    except ValueError as error:
        raise ValueError("source path must be lexically inside the repository") from error
    parts = lexical_relative.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("source path must be a direct lexical descendant")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow
    opened_directories: list[int] = []
    try:
        current = os.open(root, directory_flags)
        opened_directories.append(current)
        for part in parts[:-1]:
            current = os.open(part, directory_flags, dir_fd=current)
            opened_directories.append(current)
        descriptor = os.open(parts[-1], os.O_RDONLY | nofollow, dir_fd=current)
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("source path must be a regular file")
            if before.st_size > _MAX_SOURCE_BYTES:
                raise ValueError(f"source file exceeds the {_MAX_SOURCE_BYTES}-byte limit")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                content = stream.read(_MAX_SOURCE_BYTES + 1)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        raise ValueError(
            "source path must contain only real repository directories and a regular file"
        ) from error
    finally:
        for directory in reversed(opened_directories):
            os.close(directory)
    if len(content) > _MAX_SOURCE_BYTES:
        raise ValueError(f"source file exceeds the {_MAX_SOURCE_BYTES}-byte limit")
    if (
        (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
        or after.st_size != before.st_size
        or after.st_size != len(content)
    ):
        raise ValueError("source file changed while it was being read")
    return root.joinpath(*parts), content


class _DeferredSigint:
    """Narrow non-interruptible region for an automatic-session CLI transaction."""

    def __init__(self, *, enabled: bool) -> None:
        self.enabled = enabled and threading.current_thread() is threading.main_thread()
        self.pending = False
        self._previous: signal._HANDLER | None = None

    def __enter__(self) -> _DeferredSigint:
        if self.enabled:
            self._previous = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, self._handle)
        return self

    def _handle(self, _signum: int, _frame: FrameType | None) -> None:
        self.pending = True

    def __exit__(self, *_: object) -> None:
        if self.enabled and self._previous is not None:
            signal.signal(signal.SIGINT, self._previous)


__all__ = ["CommandRequest", "SourceIndexError", "execute"]
