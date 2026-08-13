from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src" / "study_agent"
INDEPENDENT = ("domain", "state", "skills", "playbooks")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_core_owners_do_not_reverse_import_capability_gateway_or_runtime_sdks() -> None:
    forbidden = (
        "study_agent.capabilities",
        "openai",
        "anthropic",
        "fastapi",
        "streamlit",
    )
    violations: list[str] = []
    for package_name in INDEPENDENT:
        package = SOURCE_ROOT / package_name
        for path in sorted(package.rglob("*.py")):
            for imported in sorted(_imports(path)):
                if any(
                    imported == prefix or imported.startswith(f"{prefix}.") for prefix in forbidden
                ):
                    violations.append(f"{path.relative_to(PROJECT_ROOT)} imports {imported}")
    assert violations == []


def test_capability_gateway_does_not_import_tools_or_product_layers() -> None:
    package = SOURCE_ROOT / "capabilities"
    forbidden = (
        "study_agent.tools.registry",
        "study_agent.cli",
        "study_agent.adapters",
        "study_agent.application",
        "study_agent.sessions",
        "study_agent.study_context",
        "sbobby_web",
    )
    violations = [
        f"{path.relative_to(PROJECT_ROOT)} imports {imported}"
        for path in sorted(package.rglob("*.py"))
        for imported in sorted(_imports(path))
        if any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in forbidden)
    ]
    assert violations == []


def test_capability_registration_has_no_import_time_discovery_path() -> None:
    forbidden_imports = {
        "importlib",
        "importlib.metadata",
        "pkg_resources",
        "pkgutil",
    }
    forbidden_source_tokens = (
        "entry_points(",
        "iter_entry_points(",
        "iter_modules(",
        "walk_packages(",
    )
    violations: list[str] = []
    for path in sorted((SOURCE_ROOT / "capabilities").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        imports = _imports(path)
        for imported in sorted(imports & forbidden_imports):
            violations.append(f"{path.relative_to(PROJECT_ROOT)} imports {imported}")
        for token in forbidden_source_tokens:
            if token in source:
                violations.append(f"{path.relative_to(PROJECT_ROOT)} uses {token}")
    assert violations == []


def test_public_capability_facade_loads_without_provider_or_transport_modules() -> None:
    blocked = (
        "openai",
        "anthropic",
        "fastapi",
        "httpx",
        "requests",
        "mcp",
    )
    script = """
import builtins
import json
import sys

blocked = BLOCKED_MODULES
real_import = builtins.__import__

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if any(name == prefix or name.startswith(prefix + ".") for prefix in blocked):
        raise ModuleNotFoundError(name)
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = guarded_import
import study_agent.api.capabilities
loaded = sorted(
    name
    for name in sys.modules
    if any(name == prefix or name.startswith(prefix + ".") for prefix in blocked)
)
print(json.dumps(loaded))
""".replace("BLOCKED_MODULES", repr(blocked))
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    process = subprocess.run(
        (sys.executable, "-c", script),
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert process.stderr == ""
    assert json.loads(process.stdout) == []


def test_capability_modules_keep_provider_and_model_ports_out_of_the_core_boundary() -> None:
    forbidden = (
        "study_agent.ports.model",
        "study_agent.ports.tutor_runner",
        "openai",
        "anthropic",
        "fastapi",
        "streamlit",
    )
    violations = [
        f"{path.relative_to(PROJECT_ROOT)} imports {imported}"
        for path in sorted((SOURCE_ROOT / "capabilities").rglob("*.py"))
        for imported in sorted(_imports(path))
        if any(imported == prefix or imported.startswith(f"{prefix}.") for prefix in forbidden)
    ]
    assert violations == []
