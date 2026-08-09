from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import pytest

from study_agent.api import authority

PROJECT_ROOT = Path(__file__).parents[2]


def test_public_authority_facade_has_no_provider_or_persistence_imports() -> None:
    source = (PROJECT_ROOT / "src/study_agent/api/authority.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert not any(
        module == "sqlite3"
        or module.startswith("study_agent.adapters")
        or module.startswith("openai")
        for module in modules
    )
    assert authority.PrincipalKind.__module__ == "study_agent.domain.events"


def test_authority_issuer_and_gate_are_distinct_capabilities() -> None:
    issuer = authority.HostAuthority()
    context = issuer.issue(
        authority.PrincipalKind.HUMAN,
        "human",
        grants=("study:write",),
        correlation_id="corr",
    )
    assert type(cast(object, issuer.port)) is not type(issuer)
    assert not hasattr(issuer.port, "issue")
    issuer.port.require(context, ("study:write",))


def test_model_durable_guard_has_no_schema_or_adapter_side_effects() -> None:
    issuer = authority.HostAuthority()
    context = issuer.issue(
        authority.PrincipalKind.MODEL,
        "model",
        grants=("study:write",),
        correlation_id="corr",
    )
    called: list[str] = []
    with pytest.raises(authority.UnauthorizedFailure):
        issuer.port.require_durable(
            context,
            ("study:write",),
            schema_validator=lambda: called.append("schema"),
            adapter=lambda: called.append("adapter"),
        )
    assert called == []
