"""Verify the exact PF-10 distribution metadata and archive ownership."""

from __future__ import annotations

import configparser
import sys
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

from _common import VERSION, run_probe

SCRIPTS = {
    "study-agent",
    "study-agent-demo",
    "study-agent-shell",
    "study-agent-shell-web",
}


def _check(root: Path, wheel: Path, sdist: Path) -> dict[str, object]:
    with zipfile.ZipFile(wheel) as archive:
        names = tuple(archive.namelist())
        wheel_file_count = len(names)
        roots = {
            name.split("/", 1)[0]
            for name in names
            if "/" in name and not name.split("/", 1)[0].endswith(".dist-info")
        }
        metadata_name = next(
            name for name in names if name.endswith(".dist-info/METADATA")
        )
        metadata = BytesParser().parsebytes(archive.read(metadata_name))
        entry_name = next(
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        )
        entries = configparser.ConfigParser()
        entries.read_string(archive.read(entry_name).decode("utf-8"))
    requirements = metadata.get_all("Requires-Dist", [])
    if metadata["Name"] != "study-agent-harness" or metadata["Version"] != VERSION:
        raise ValueError("wheel name/version metadata does not match the release")
    if roots != {"study_agent"}:
        raise ValueError(f"wheel owns unexpected regular namespaces: {sorted(roots)}")
    if set(entries["console_scripts"]) != SCRIPTS:
        raise ValueError("wheel entry-point ownership does not match the release")
    if any("extra ==" not in requirement for requirement in requirements):
        raise ValueError("base distribution has a mandatory dependency")
    with tarfile.open(sdist, "r:gz") as archive:
        sdist_names = tuple(archive.getnames())
    forbidden = ("/tests/", "/dev/", "/.worktrees/")
    if any(marker in name for name in sdist_names for marker in forbidden):
        raise ValueError("sdist contains checkout-only material")
    return {
        "base_dependencies": [],
        "entry_points": sorted(SCRIPTS),
        "regular_namespaces": sorted(roots),
        "sdist_files": len(sdist_names),
        "wheel_files": wheel_file_count,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_distribution.py DIST_DIR")
    raise SystemExit(run_probe("distribution", sys.argv[1], _check))
