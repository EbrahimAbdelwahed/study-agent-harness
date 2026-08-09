from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"


def test_public_imports_do_not_load_rejected_provider_or_product_modules() -> None:
    script = """
import json
import sys
import study_agent
import study_agent.tools

blocked = (
    "openai",
    "study_agent.api",
    "study_agent.runtime",
    "study_agent.recall",
    "study_agent.scheduling",
    "study_agent.adapters.scheduling",
    "study_agent.adapters.workarounds",
    "study_agent.pdf",
    "study_agent.adapters.pdf",
    "study_agent.shell",
    "study_agent.adapters.shell",
    "study_agent.browser",
    "study_agent.adapters.browser",
    "study_agent.demo.product_shell",
    "study_agent.demo.browser",
    "study_agent.ui",
    "study_agent.product",
    "sbobby",
)
loaded = sorted(
    name
    for name in sys.modules
    if any(name == prefix or name.startswith(prefix + ".") for prefix in blocked)
)
print(json.dumps(loaded))
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(SOURCE_ROOT)
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
