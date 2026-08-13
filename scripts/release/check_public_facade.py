"""Install the release wheel and verify its root/public manifest boundary."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from typing import cast

from _common import VERSION, run_probe


def _python(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _check(root: Path, wheel: Path, sdist: Path) -> dict[str, object]:
    del root, sdist
    with tempfile.TemporaryDirectory(prefix="study-agent-pf10-facade-") as temporary:
        environment = Path(temporary) / "venv"
        clean_env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONPATH", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"}
        }
        uv = shutil.which("uv")
        if uv is not None:
            clean_env["UV_CACHE_DIR"] = str(Path(temporary) / "uv-cache")
            subprocess.run(
                [uv, "venv", "--python", sys.executable, str(environment)],
                check=True,
                cwd=temporary,
                env=clean_env,
                capture_output=True,
                text=True,
            )
            install = [
                uv,
                "pip",
                "install",
                "--python",
                str(_python(environment)),
                "--no-deps",
                str(wheel),
            ]
        else:
            venv.EnvBuilder(with_pip=True).create(environment)
            install = [
                str(_python(environment)),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-deps",
                str(wheel),
            ]
        subprocess.run(
            install,
            check=True,
            cwd=temporary,
            env=clean_env,
            capture_output=True,
            text=True,
        )
        code = (
            "import json,study_agent;"
            "from study_agent.api import public_manifest;"
            "m=public_manifest();"
            "print(json.dumps({'version':study_agent.__version__,"
            "'manifest_version':m.package_version,'fingerprint':m.fingerprint,"
            "'root_exports':list(study_agent.__all__),"
            "'subfacades':list(m.subfacades)},sort_keys=True))"
        )
        result = subprocess.run(
            [str(_python(environment)), "-I", "-c", code],
            check=True,
            cwd=temporary,
            env=clean_env,
            capture_output=True,
            text=True,
        )
    payload = cast(dict[str, object], json.loads(result.stdout))
    if payload["version"] != VERSION or payload["manifest_version"] != VERSION:
        raise ValueError("installed root and manifest versions do not match 0.3.0")
    if payload["root_exports"] != ["__version__", "api"]:
        raise ValueError("installed root exports exceed the approved facade")
    return payload


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_public_facade.py DIST_DIR")
    raise SystemExit(run_probe("public_facade", sys.argv[1], _check))
