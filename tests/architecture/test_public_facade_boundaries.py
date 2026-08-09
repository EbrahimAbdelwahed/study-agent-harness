from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from study_agent import api

PROJECT_ROOT = Path(__file__).parents[2]
BLOCKED_PREFIXES = (
    "openai",
    "anthropic",
    "study_agent.adapters",
    "study_agent.cli",
    "study_agent.demo",
    "study_agent.filesystem",
    "study_agent.ui",
    "study_agent.telemetry",
    "fsrs",
)


def test_every_listed_subfacade_is_importable_without_optional_modules() -> None:
    for name in api.public_manifest().subfacades:
        module = __import__(f"study_agent.api.{name}", fromlist=["*"])
        assert module.__all__ == ()
        assert {item for item in dir(module) if not item.startswith("_")} == set()


def test_root_import_stays_clean_when_optional_imports_are_unavailable() -> None:
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
import study_agent
manifest = study_agent.api.public_manifest()
for name in manifest.subfacades:
    __import__(f"study_agent.api.{name}")

loaded = sorted(
    name
    for name in sys.modules
    if any(name == prefix or name.startswith(prefix + ".") for prefix in blocked)
)
print(json.dumps({"loaded": loaded, "fingerprint": manifest.fingerprint}))
""".replace("BLOCKED_MODULES", repr(BLOCKED_PREFIXES))
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
    result = json.loads(process.stdout)
    assert result["loaded"] == []
    assert result["fingerprint"] == api.public_manifest().fingerprint
