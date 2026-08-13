from __future__ import annotations

import asyncio
import csv
import importlib.metadata
import importlib.util
import os
from hashlib import sha256
from pathlib import Path

import pytest
from packaging.requirements import Requirement

from study_agent.adapters.host import (
    OpenAIResponsesTutorConfig,
    OpenAIResponsesTutorDecisionPort,
)
from study_agent.adapters.package_trust import PackageTrustBinding
from study_agent.hosts import AdvertisedCapability, TutorHostContext, validate_decision

_SHA = "a" * 64


def _context() -> TutorHostContext:
    return TutorHostContext(
        "build-week-smoke",
        "build-week-smoke-session",
        1,
        1,
        {"status": "active"},
        {"estimates": ()},
        (
            AdvertisedCapability(
                "grounding.ask",
                "grounding.ask@1.0.0",
                _SHA,
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


class _NoInterruption:
    def is_interrupted(self) -> bool:
        return False


def _host_binding(package_name: str, expected_version: str) -> PackageTrustBinding:
    """Compose one explicit RECORD-bound graph as the embedding host would."""

    pending = [package_name]
    distributions: dict[str, importlib.metadata.Distribution] = {}
    root: Path | None = None
    while pending:
        name = pending.pop()
        try:
            distribution = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError as error:
            pytest.skip(f"host dependency {name!r} is not installed: {error}")
        key = distribution.metadata.get("Name", name).lower().replace("-", "_")
        if key in distributions:
            continue
        candidate_root = Path(str(distribution.locate_file(""))).resolve()
        if root is None:
            root = candidate_root
        elif candidate_root != root:
            pytest.skip("optional distribution graph spans multiple package roots")
        distributions[key] = distribution
        for requirement_text in distribution.requires or ():
            requirement = Requirement(requirement_text)
            if requirement.marker is not None and not requirement.marker.evaluate():
                continue
            pending.append(requirement.name)

    assert root is not None
    manifest: dict[str, tuple[str, int]] = {}
    for distribution in distributions.values():
        record = distribution.read_text("RECORD")
        if record is None:
            pytest.fail(f"{distribution.metadata.get('Name', '?')} has no RECORD")
        for row in csv.reader(record.splitlines()):
            if len(row) != 3 or not row[0] or "\\" in row[0]:
                pytest.fail("host RECORD contains an invalid path")
            relative = Path(row[0])
            if relative.is_absolute() or any(
                part in ("", ".", "..") for part in relative.parts
            ):
                pytest.fail("host RECORD contains a non-portable path")
            path = root / relative
            if not path.is_file() or path.is_symlink():
                pytest.fail(f"host RECORD file is unavailable: {row[0]}")
            value = path.read_bytes()
            manifest[relative.as_posix()] = (sha256(value).hexdigest(), len(value))
    return PackageTrustBinding.from_manifest(
        package_name, root, expected_version, manifest
    )


@pytest.mark.skipif(
    not os.environ.get("STUDY_AGENT_OPENAI_SMOKE")
    or not os.environ.get("STUDY_AGENT_OPENAI_SMOKE_MODEL")
    or not os.environ.get("OPENAI_API_KEY")
    or importlib.util.find_spec("openai") is None,
    reason="opt-in OpenAI Responses smoke requires the SDK, model, and API key",
)
def test_openai_responses_smoke_is_opt_in() -> None:
    model = os.environ["STUDY_AGENT_OPENAI_SMOKE_MODEL"]
    port = OpenAIResponsesTutorDecisionPort(
        OpenAIResponsesTutorConfig(
            model,
            "OPENAI_API_KEY",
            timeout_seconds=20.0,
            max_output_tokens=128,
        ),
        package_trust=_host_binding(
            "openai", importlib.metadata.version("openai")
        ),
    )
    decision = asyncio.run(port.decide(_context(), _NoInterruption()))
    validate_decision(decision, _context())
