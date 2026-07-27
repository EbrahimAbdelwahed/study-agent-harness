from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2] / "src" / "study_agent"


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_substrate_domain_contract_has_no_adapter_provider_or_model_imports() -> None:
    forbidden = (
        "study_agent.adapters",
        "study_agent.application",
        "study_agent.cli",
        "study_agent.connectors",
        "study_agent.models",
        "study_agent.providers",
        "openai",
        "anthropic",
        "deepseek",
        "httpx",
        "requests",
        "sqlite3",
        "socket",
    )
    paths = (
        ROOT / "domain" / "substrate.py",
        ROOT / "domain" / "identifiers.py",
        ROOT / "domain" / "tree.py",
    )
    violations = {
        str(path.relative_to(ROOT)): imported
        for path in paths
        for imported in imports(path)
        if any(imported == prefix or imported.startswith(prefix + ".") for prefix in forbidden)
    }
    assert violations == {}


def test_knowledge_package_stays_pure_offline_and_connector_free() -> None:
    forbidden = (
        "study_agent.adapters",
        "study_agent.application",
        "study_agent.cli",
        "study_agent.connectors",
        "study_agent.hosts",
        "study_agent.ingestion",
        "study_agent.models",
        "study_agent.providers",
        "study_agent.retrieval",
        "openai",
        "anthropic",
        "httpx",
        "requests",
        "pathlib",
        "sqlite3",
        "socket",
    )
    violations = {
        str(path.relative_to(ROOT)): imported
        for path in sorted((ROOT / "knowledge").rglob("*.py"))
        for imported in imports(path)
        if any(imported == prefix or imported.startswith(prefix + ".") for prefix in forbidden)
    }
    assert violations == {}


def test_document_tree_contracts_are_owned_by_the_domain_and_knowledge_modules() -> None:
    from study_agent.domain import DialectProfile, DocumentTree, RegionKind, TreeNode
    from study_agent.knowledge.tree import build_document_tree

    assert DocumentTree.__module__ == "study_agent.domain.tree"
    assert TreeNode.__module__ == "study_agent.domain.tree"
    assert RegionKind.__module__ == "study_agent.domain.tree"
    assert DialectProfile.__module__ == "study_agent.domain.tree"
    assert build_document_tree.__module__ == "study_agent.knowledge.tree"


def test_substrate_modules_do_not_define_a_second_byte_store_or_filesystem_owner() -> None:
    paths = (
        ROOT / "domain" / "substrate.py",
        ROOT / "ingestion" / "substrate.py",
        ROOT / "ingestion" / "substrate_events.py",
        ROOT / "ingestion" / "substrate_projection.py",
    )
    forbidden_class_names = {"BlobStore", "FilesystemBlobStore", "SQLiteEventStore"}
    forbidden_effect_methods = {"open", "write", "unlink", "rename", "mkdir"}
    violations: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in forbidden_class_names:
                violations.append(f"{path.relative_to(ROOT)} defines {node.name}")
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in forbidden_effect_methods
            ):
                violations.append(f"{path.relative_to(ROOT)} defines {node.name}")
    assert violations == []


def test_public_substrate_types_are_owned_by_domain_and_ingestion_modules() -> None:
    from study_agent.domain import PageMapEntry, Substrate, SubstrateProduction
    from study_agent.ingestion.substrate import ConverterReceipt, SubstrateProductionService

    assert PageMapEntry.__module__ == "study_agent.domain.substrate"
    assert Substrate.__module__ == "study_agent.domain.substrate"
    assert SubstrateProduction.__module__ == "study_agent.domain.substrate"
    assert ConverterReceipt.__module__ == "study_agent.ingestion.substrate"
    assert SubstrateProductionService.__module__ == "study_agent.ingestion.substrate"


def test_no_module_outside_the_domain_defines_a_parallel_unit_type() -> None:
    owned = {"units.py"}
    parallel: list[str] = []
    for path in sorted(ROOT.rglob("*.py")):
        if path.parent == ROOT / "domain" and path.name in owned:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in {
                "RetrievableUnit",
                "UnitKind",
                "UnitMeta",
                "CanonicalRef",
            }:
                parallel.append(f"{path.relative_to(ROOT)} defines {node.name}")
    assert parallel == []


def test_retrievable_unit_contracts_are_owned_by_domain_and_knowledge() -> None:
    from study_agent.domain import RetrievableUnit, UnitKind, UnitMeta
    from study_agent.knowledge.units import reduce_units

    assert RetrievableUnit.__module__ == "study_agent.domain.units"
    assert UnitKind.__module__ == "study_agent.domain.units"
    assert UnitMeta.__module__ == "study_agent.domain.units"
    assert reduce_units.__module__ == "study_agent.knowledge.units"


def test_projection_contracts_are_owned_by_domain_and_pure_knowledge() -> None:
    from study_agent.domain import (
        IndexProjection,
        ProjectionId,
        ProjectionRef,
        ProjectorManifest,
        ProjectorPort,
    )
    from study_agent.knowledge.projections import StructuralProjector, reduce_projections

    assert IndexProjection.__module__ == "study_agent.domain.projections"
    assert ProjectionId.__module__ == "study_agent.domain.projections"
    assert ProjectionRef.__module__ == "study_agent.domain.projections"
    assert ProjectorManifest.__module__ == "study_agent.domain.projections"
    assert getattr(ProjectorPort, "__module__", "") == "study_agent.domain.projections"
    assert StructuralProjector.__module__ == "study_agent.knowledge.projections"
    assert reduce_projections.__module__ == "study_agent.knowledge.projections"


def test_projection_modules_do_not_import_provider_or_adapter_layers() -> None:
    forbidden = (
        "study_agent.adapters",
        "study_agent.application",
        "study_agent.connectors",
        "study_agent.ingestion",
        "study_agent.models",
        "study_agent.providers",
        "openai",
        "anthropic",
        "deepseek",
        "httpx",
        "requests",
        "sqlite3",
        "socket",
    )
    paths = (ROOT / "domain" / "projections.py", ROOT / "knowledge" / "projections.py")
    violations = {
        str(path.relative_to(ROOT)): imported
        for path in paths
        for imported in imports(path)
        if any(imported == prefix or imported.startswith(prefix + ".") for prefix in forbidden)
    }
    assert violations == {}
