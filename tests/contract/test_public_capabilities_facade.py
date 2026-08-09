from __future__ import annotations

import json
import os
import subprocess
import sys

import study_agent.api.capabilities as facade
from study_agent.capabilities import bindings, contracts, gateway, registry

PUBLIC_NAMES = (
    "CapabilityBinding",
    "CapabilityContinuation",
    "CapabilityDependencyResolver",
    "CapabilityGatewayError",
    "CapabilityGatewayErrorCode",
    "CapabilityId",
    "CapabilityIdentifier",
    "CapabilityManifest",
    "CapabilityOutcome",
    "CapabilityOutcomeStatus",
    "CapabilityRequest",
    "CancelledCapabilityOutcome",
    "CompletedCapabilityOutcome",
    "FailedCapabilityOutcome",
    "StaleCapabilityOutcome",
    "StudyCapabilityGateway",
    "StudyCapabilityRegistry",
    "SuspendedCapabilityOutcome",
    "TerminatedCapabilityOutcome",
    "TutorCapabilityId",
    "encode_capability_outcome",
)


def test_facade_exports_only_provider_neutral_capability_contracts() -> None:
    expected = {
        "CapabilityBinding": bindings.CapabilityBinding,
        "CapabilityContinuation": contracts.CapabilityContinuation,
        "CapabilityDependencyResolver": bindings.CapabilityDependencyResolver,
        "CapabilityGatewayError": contracts.CapabilityGatewayError,
        "CapabilityGatewayErrorCode": contracts.CapabilityGatewayErrorCode,
        "CapabilityId": contracts.CapabilityId,
        "CapabilityIdentifier": contracts.CapabilityIdentifier,
        "CapabilityManifest": contracts.CapabilityManifest,
        "CapabilityOutcome": contracts.CapabilityOutcome,
        "CapabilityOutcomeStatus": contracts.CapabilityOutcomeStatus,
        "CapabilityRequest": contracts.CapabilityRequest,
        "CancelledCapabilityOutcome": contracts.CancelledCapabilityOutcome,
        "CompletedCapabilityOutcome": contracts.CompletedCapabilityOutcome,
        "FailedCapabilityOutcome": contracts.FailedCapabilityOutcome,
        "StaleCapabilityOutcome": contracts.StaleCapabilityOutcome,
        "StudyCapabilityGateway": gateway.StudyCapabilityGateway,
        "StudyCapabilityRegistry": registry.StudyCapabilityRegistry,
        "SuspendedCapabilityOutcome": contracts.SuspendedCapabilityOutcome,
        "TerminatedCapabilityOutcome": contracts.TerminatedCapabilityOutcome,
        "TutorCapabilityId": contracts.TutorCapabilityId,
        "encode_capability_outcome": contracts.encode_capability_outcome,
    }

    assert facade.__all__ == ()
    assert tuple(sorted(expected)) == tuple(sorted(PUBLIC_NAMES))
    assert {name for name in dir(facade) if not name.startswith("_")} == set()
    for name, implementation in expected.items():
        assert getattr(facade, name) is implementation

    for name in ("builtin_capability_bindings", "FlashcardCapabilityDispatcher"):
        assert not hasattr(facade, name)


def test_facade_import_does_not_load_provider_or_discovery_modules() -> None:
    script = """
import builtins
import importlib.metadata
import json
import sys

blocked = BLOCKED_MODULES
real_import = builtins.__import__

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if any(name == prefix or name.startswith(prefix + ".") for prefix in blocked):
        raise ModuleNotFoundError(name)
    return real_import(name, globals, locals, fromlist, level)

def forbidden(*args, **kwargs):
    raise AssertionError("capability facade attempted plugin discovery")

builtins.__import__ = guarded_import
importlib.metadata.entry_points = forbidden
import study_agent.api.capabilities as facade

loaded = sorted(
    name
    for name in sys.modules
    if any(name == prefix or name.startswith(prefix + ".") for prefix in blocked)
)
print(json.dumps({"loaded": loaded, "exports": list(facade.__all__)}))
""".replace(
        "BLOCKED_MODULES", repr(("openai", "anthropic", "fastapi", "httpx", "requests", "mcp"))
    )
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    process = subprocess.run(
        (sys.executable, "-s", "-c", script),
        cwd="/tmp",
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    assert process.stderr == ""
    assert json.loads(process.stdout) == {"loaded": [], "exports": []}
