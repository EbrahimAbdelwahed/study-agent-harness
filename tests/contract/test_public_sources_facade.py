from __future__ import annotations

import subprocess
import sys

import study_agent.api.sources as sources

EXPECTED_EXPORTS = {
    "BlobRef",
    "Citation",
    "CitationFailure",
    "CitationFailureKind",
    "DerivedRef",
    "FIGURE_CITATION_VERSION",
    "FigureCitationV1",
    "SourceRevision",
    "SourceRevisionRef",
    "SubstrateRef",
    "TEXT_CITATION_VERSION",
    "TextCitationV2",
    "citation_from_bytes",
    "citation_from_json",
}


def test_sources_facade_exports_only_frozen_source_and_citation_contracts() -> None:
    assert set(sources.__all__) == EXPECTED_EXPORTS
    assert {
        name for name in dir(sources) if not name.startswith("_")
    } == EXPECTED_EXPORTS

    for name in EXPECTED_EXPORTS:
        assert hasattr(sources, name)

    for contract in (
        sources.BlobRef,
        sources.SourceRevision,
        sources.SourceRevisionRef,
        sources.SubstrateRef,
        sources.TextCitationV2,
        sources.FigureCitationV1,
        sources.DerivedRef,
    ):
        assert contract.__dataclass_params__.frozen


def test_sources_facade_does_not_import_optional_provider_modules() -> None:
    script = r'''
import builtins
import json
import sys

blocked = {
    "anthropic",
    "fsrs",
    "openai",
    "study_agent.adapters",
    "study_agent.cli",
    "study_agent.demo",
    "study_agent.filesystem",
    "study_agent.telemetry",
    "study_agent.ui",
}
real_import = builtins.__import__


def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if any(name == prefix or name.startswith(prefix + ".") for prefix in blocked):
        raise ModuleNotFoundError(name)
    return real_import(name, globals, locals, fromlist, level)


builtins.__import__ = guarded_import
import study_agent.api.sources as sources

loaded = sorted(
    name
    for name in sys.modules
    if any(name == prefix or name.startswith(prefix + ".") for prefix in blocked)
)
print(json.dumps({"exports": sorted(sources.__all__), "loaded": loaded}))
'''
    process = subprocess.run(
        (sys.executable, "-c", script),
        cwd="/tmp",
        text=True,
        capture_output=True,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    assert process.stderr == ""
    assert process.stdout
    assert '"loaded": []' in process.stdout
