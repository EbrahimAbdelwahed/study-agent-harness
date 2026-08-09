from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

import pytest

import study_agent
from study_agent import api

PROJECT_ROOT = Path(__file__).parents[2]
EXPECTED_SUBFACADES = (
    "runtime",
    "authority",
    "storage",
    "sources",
    "capabilities",
    "artifacts",
    "assessments",
    "recall",
)


def test_public_manifest_is_frozen_and_canonically_serialized() -> None:
    manifest = api.public_manifest()

    assert isinstance(manifest, api.PublicManifest)
    assert manifest is api.public_manifest()
    assert manifest.facade_version == 1
    assert manifest.package_version == study_agent.__version__
    assert manifest.python_versions == ("3.12", "3.13")
    assert manifest.subfacades == EXPECTED_SUBFACADES
    assert manifest.exports == (
        "PublicManifest",
        "public_manifest",
        *EXPECTED_SUBFACADES,
    )
    assert isinstance(manifest.python_versions, tuple)
    assert isinstance(manifest.subfacades, tuple)
    assert isinstance(manifest.exports, tuple)
    assert isinstance(manifest.schema_versions, MappingProxyType)
    assert dict(manifest.schema_versions) == {"manifest": 1}

    expected_bytes = json.dumps(
        manifest.to_json(),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    assert manifest.canonical_bytes() == expected_bytes
    assert manifest.canonical_bytes() == api.public_manifest().canonical_bytes()
    assert manifest.fingerprint == hashlib.sha256(expected_bytes).hexdigest()

    with pytest.raises(FrozenInstanceError):
        manifest.package_version = "9.9.9"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        manifest.subfacades += ("private",)  # type: ignore[misc]
    with pytest.raises(TypeError):
        manifest.schema_versions["private"] = 1  # type: ignore[index]


def test_root_and_facade_export_only_curated_names() -> None:
    assert study_agent.__all__ == ("__version__", "api")
    assert api.__all__ == (
        "PublicManifest",
        "public_manifest",
        *EXPECTED_SUBFACADES,
    )
    assert {name for name in dir(study_agent) if not name.startswith("_")} == {"api"}
    assert {
        name for name in dir(api) if not name.startswith("_")
    } == set(api.__all__)

    for name in api.__all__:
        assert hasattr(api, name)


def test_package_metadata_and_runtime_version_agree() -> None:
    metadata = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert metadata["project"]["name"] == "study-agent-harness"
    assert metadata["project"]["version"] == study_agent.__version__
    assert study_agent.__version__
