"""Run the PF-09 positive/negative downstream cycle against release artifacts."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from _common import run_probe

ROOT = Path(__file__).parents[2]


def _check(root: Path, wheel: Path, sdist: Path) -> dict[str, object]:
    del wheel, sdist
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"}
    }
    environment["STUDY_AGENT_DIST_DIR"] = str(root)
    environment["STUDY_AGENT_REQUIRE_DIST"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/contract/distribution/test_side_by_side_install.py",
        ],
        check=True,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    return {"pytest": result.stdout.strip(), "positive": "passed", "negative": "rejected"}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_side_by_side.py DIST_DIR")
    raise SystemExit(run_probe("side_by_side", sys.argv[1], _check))
