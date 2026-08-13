"""Shared deterministic helpers for the PF-10 release probes."""

from __future__ import annotations

import hashlib
import json
import sys
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

VERSION = "0.3.0"


def artifacts(root: Path) -> tuple[Path, Path]:
    wheel = tuple(root.glob(f"study_agent_harness-{VERSION}-*.whl"))
    sdist = tuple(root.glob(f"study_agent_harness-{VERSION}.tar.gz"))
    if len(wheel) != 1 or len(sdist) != 1:
        raise ValueError("release directory must contain exactly one 0.3.0 wheel and sdist")
    return wheel[0], sdist[0]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def archive_integrity(wheel: Path, sdist: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        if archive.testzip() is not None:
            raise ValueError("wheel archive failed its CRC check")
    with tarfile.open(sdist, "r:gz") as archive:
        if not archive.getnames():
            raise ValueError("sdist archive is empty")


def run_probe(
    name: str,
    root_text: str,
    check: Callable[[Path, Path, Path], dict[str, Any]],
) -> int:
    root = Path(root_text).resolve()
    report: dict[str, Any] = {
        "probe": name,
        "command": [sys.executable, *sys.argv],
        "interpreter": (
            f"{sys.version_info.major}.{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        ),
        "result": "failed",
    }
    try:
        wheel, sdist = artifacts(root)
        archive_integrity(wheel, sdist)
        report.update(
            {
                "version": VERSION,
                "wheel": wheel.name,
                "wheel_sha256": digest(wheel),
                "sdist": sdist.name,
                "sdist_sha256": digest(sdist),
                "checks": check(root, wheel, sdist),
                "known_preexisting_failures": [],
                "result": "passed",
            }
        )
    except Exception as error:
        report["failure_type"] = type(error).__name__
        report["failure"] = str(error)
        print(json.dumps(report, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0
