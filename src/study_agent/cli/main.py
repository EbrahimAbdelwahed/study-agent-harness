"""Stdlib argparse entry point for the reference CLI."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Mapping, Sequence
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Never, cast

from study_agent.application import GroundingAskError
from study_agent.domain._validation import JsonObject
from study_agent.ports import CourseNotFoundError, SessionNotFoundError

from .commands import CommandRequest, SourceIndexError, _DeferredSigint, execute
from .config import LocalConfigError, LocalRepositoryConfig, ModelAdapterConfig
from .output import CommandOutcome, emit_error, emit_success
from .repository import (
    LocalRepositoryError,
    ModelAdapterConfigurationError,
    ModelAdapterRegistry,
)


class CliArgumentError(ValueError):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise CliArgumentError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="study-agent", description="Local event-sourced study harness")
    parser.add_argument("--repository", type=Path, default=Path.cwd(), help="repository root")
    parser.add_argument("--json", action="store_true", help="emit one JSON document")
    sub = parser.add_subparsers(dest="group", required=True)

    init = sub.add_parser("init", help="initialize an offline local repository")
    init.add_argument("directory", type=Path)
    init.add_argument("--model-adapter")
    init.add_argument(
        "--model-setting",
        action="append",
        default=[],
        metavar="NAME=JSON",
        help="technical adapter setting; repeat for multiple values",
    )
    init.add_argument("--credential-env", help="environment-variable name, never its value")

    course = sub.add_parser("course", help="course commands").add_subparsers(
        dest="action", required=True
    )
    create = course.add_parser("create", help="create an immutable course profile")
    create.add_argument("--course-id")
    create.add_argument("--title", required=True)
    create.add_argument("--language", default="en")
    create.add_argument("--exam-date")
    create.add_argument("--learning-goal", dest="learning_goals", action="append", required=True)
    create.add_argument("--assessment-style", dest="assessment_styles", action="append", default=[])

    source = sub.add_parser("source", help="source commands").add_subparsers(
        dest="action", required=True
    )
    add = source.add_parser("add", help="ingest a text or Markdown source")
    add.add_argument("course_id")
    add.add_argument("path")
    add.add_argument("--source-id")
    add.add_argument("--title")
    add.add_argument("--trust-level", type=int, default=50)
    add.add_argument("--source-role", default="course_material")
    listing = source.add_parser("list", help="list canonical source revisions")
    listing.add_argument("course_id")

    ask = sub.add_parser("ask", help="ask a grounded question")
    ask.add_argument("course_id")
    ask.add_argument("question")
    ask.add_argument("--session-id")
    ask.add_argument("--idempotency-key")

    session = sub.add_parser("session", help="session commands").add_subparsers(
        dest="action", required=True
    )
    session_list = session.add_parser("list", help="list sessions for a course")
    session_list.add_argument("course_id")
    resume = session.add_parser("resume", help="resume an explicitly identified session")
    resume.add_argument("course_id")
    resume.add_argument("session_id")

    export = sub.add_parser("export", help="write deterministic export v1")
    export.add_argument("course_id")
    export.add_argument("--output", required=True)
    sub.add_parser("doctor", help="run offline integrity diagnostics")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    model_adapters: ModelAdapterRegistry | None = None,
    environment: Mapping[str, str] | None = None,
) -> int:
    raw = tuple(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in raw
    try:
        parse_arguments = tuple(item for item in raw if item != "--json")
        if json_mode and any(item in {"-h", "--help"} for item in parse_arguments):
            help_stream = StringIO()
            try:
                with redirect_stdout(help_stream):
                    build_parser().parse_args(parse_arguments)
            except SystemExit as error:
                if error.code != 0:
                    raise
            emit_success(
                CommandOutcome("help", {"text": help_stream.getvalue()}),
                json_mode=True,
            )
            return 0
        namespace = build_parser().parse_args(parse_arguments)
        namespace.json = json_mode
        request = _request(namespace)
        # Auto-session creation and its run live in separate durable stores. Treat the
        # complete authoritative host operation, including its success emission, as one
        # narrow SIGINT-deferred region: success wins once canonical work has committed.
        with _DeferredSigint(enabled=_automatic_session_ask(request)):
            if model_adapters is None and environment is None:
                outcome = asyncio.run(execute(request))
            else:
                outcome = asyncio.run(
                    execute(
                        request,
                        model_adapters=model_adapters,
                        environment=None if environment is None else dict(environment),
                    )
                )
            emit_success(outcome, json_mode=json_mode)
    except KeyboardInterrupt:
        emit_error(
            "interrupted",
            "operation interrupted; no cancellation transition was fabricated",
            json_mode=json_mode,
        )
        return 130
    except SourceIndexError as error:
        emit_error(
            "index_rebuild_failed",
            str(error),
            json_mode=json_mode,
            details={"canonical_source": error.committed},
        )
        return 4
    except ModelAdapterConfigurationError:
        emit_error(
            "model_unavailable",
            "configured model adapter is unavailable",
            json_mode=json_mode,
        )
        return 4
    except (LocalConfigError, LocalRepositoryError):
        emit_error(
            "repository_error",
            "local repository is absent or incompatible",
            json_mode=json_mode,
        )
        return 4
    except (CliArgumentError, ValueError, TypeError) as error:
        emit_error("invalid_request", _safe_message(error), json_mode=json_mode)
        return 2
    except (CourseNotFoundError, SessionNotFoundError, FileNotFoundError) as error:
        del error
        emit_error(
            "not_found",
            "requested canonical or local resource was not found",
            json_mode=json_mode,
        )
        return 3
    except GroundingAskError as error:
        emit_error(error.code.value, str(error), json_mode=json_mode)
        return 4
    except (OSError, RuntimeError):
        emit_error(
            "operational_failure",
            "operation could not be completed safely",
            json_mode=json_mode,
        )
        return 4
    return 0


def _request(namespace: argparse.Namespace) -> CommandRequest:
    values = vars(namespace).copy()
    repository = Path(values.pop("repository"))
    values.pop("json", None)
    group = str(values.pop("group"))
    action = values.pop("action", None)
    if group == "init":
        repository = Path(values.pop("directory"))
        values["config"] = _init_config(values)
        name = "init"
    elif action is not None:
        name = f"{group}.{action}"
    else:
        name = group
    return CommandRequest(repository, name, values)


def _init_config(values: dict[str, object]) -> LocalRepositoryConfig:
    adapter = values.pop("model_adapter")
    raw_settings = values.pop("model_setting")
    credential_env = values.pop("credential_env")
    if adapter is None:
        if raw_settings or credential_env is not None:
            raise CliArgumentError("model settings require --model-adapter")
        return LocalRepositoryConfig()
    if not isinstance(adapter, str) or not isinstance(raw_settings, list):
        raise CliArgumentError("model adapter configuration is invalid")
    settings: dict[str, object] = {}
    for assignment in raw_settings:
        if not isinstance(assignment, str) or "=" not in assignment:
            raise CliArgumentError("--model-setting must use NAME=JSON")
        key, payload = assignment.split("=", 1)
        if not key or key in settings:
            raise CliArgumentError("model setting names must be non-empty and unique")
        try:
            settings[key] = json.loads(payload)
        except json.JSONDecodeError as error:
            raise CliArgumentError("model setting values must be JSON") from error
    return LocalRepositoryConfig(
        ModelAdapterConfig(
            adapter,
            cast(JsonObject, settings),
            None if credential_env is None else str(credential_env),
        )
    )


def _safe_message(error: BaseException) -> str:
    message = str(error).strip()
    return message if message and "api" not in message.lower() else "request is invalid"


def _automatic_session_ask(request: CommandRequest) -> bool:
    return request.name == "ask" and request.values.get("session_id") is None


def color_enabled() -> bool:
    """CLI semantics never depend on color; this exposes the conventional policy."""
    return "NO_COLOR" not in os.environ and sys.stdout.isatty()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["build_parser", "color_enabled", "main"]
