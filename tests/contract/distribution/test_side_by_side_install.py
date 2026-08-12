from __future__ import annotations

import configparser
import csv
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tomllib
import venv
import zipfile
from email.parser import BytesParser
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
FIXTURES = ROOT / "tests/fixtures/distribution"
HARNESS_SCRIPTS = {
    "study-agent",
    "study-agent-demo",
    "study-agent-shell",
    "study-agent-shell-web",
}


def _artifacts() -> tuple[Path, Path]:
    root = Path(os.environ.get("STUDY_AGENT_DIST_DIR", ROOT / "dist")).resolve()
    wheels = tuple(root.glob("study_agent_harness-*.whl"))
    sdists = tuple(root.glob("study_agent_harness-*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        pytest.skip("PF-09 requires one wheel and one sdist in STUDY_AGENT_DIST_DIR")
    return wheels[0], sdists[0]


def _build_fixture(source: Path, output: Path) -> Path:
    output.mkdir(parents=True)
    project = tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    distribution = project["name"].replace("-", "_")
    version = project["version"]
    wheel = output / f"{distribution}-{version}-py3-none-any.whl"
    dist_info = f"{distribution}-{version}.dist-info"
    members: dict[str, bytes] = {}
    for path in sorted((source / "src").rglob("*.py")):
        members[path.relative_to(source / "src").as_posix()] = path.read_bytes()
    members[f"{dist_info}/METADATA"] = (
        "Metadata-Version: 2.4\n"
        f"Name: {project['name']}\n"
        f"Version: {version}\n"
        f"Requires-Python: {project['requires-python']}\n\n"
    ).encode()
    members[f"{dist_info}/WHEEL"] = (
        b"Wheel-Version: 1.0\nGenerator: pf09-contract\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    )
    scripts = project.get("scripts", {})
    if scripts:
        body = "[console_scripts]\n" + "".join(
            f"{name} = {target}\n" for name, target in sorted(scripts.items())
        )
        members[f"{dist_info}/entry_points.txt"] = body.encode()
    packages = sorted({name.split("/", 1)[0] for name in members if "/" in name})
    members[f"{dist_info}/top_level.txt"] = ("\n".join(packages) + "\n").encode()
    record = io.StringIO()
    writer = csv.writer(record, lineterminator="\n")
    for name in sorted(members):
        writer.writerow((name, "", ""))
    writer.writerow((f"{dist_info}/RECORD", "", ""))
    members[f"{dist_info}/RECORD"] = record.getvalue().encode()
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(members.items()):
            archive.writestr(name, data)
    return wheel


def _wheel_ownership(wheel: Path) -> tuple[frozenset[str], frozenset[str]]:
    with zipfile.ZipFile(wheel) as archive:
        names = tuple(archive.namelist())
        packages = frozenset(
            name.split("/", 1)[0]
            for name in names
            if "/" in name and not name.split("/", 1)[0].endswith(".dist-info")
        )
        entry_name = next(
            (name for name in names if name.endswith(".dist-info/entry_points.txt")),
            None,
        )
        parser = configparser.ConfigParser()
        if entry_name is not None:
            parser.read_string(archive.read(entry_name).decode("utf-8"))
        scripts = (
            frozenset(parser["console_scripts"])
            if parser.has_section("console_scripts")
            else frozenset()
        )
    return packages, scripts


def _assert_collision_free(downstream: Path) -> None:
    packages, scripts = _wheel_ownership(downstream)
    duplicate_packages = packages & {"study_agent"}
    duplicate_scripts = scripts & HARNESS_SCRIPTS
    if duplicate_packages or duplicate_scripts:
        raise RuntimeError(
            "downstream distribution collides with Harness ownership: "
            f"packages={sorted(duplicate_packages)}, scripts={sorted(duplicate_scripts)}"
        )


def _assert_harness_ownership(wheel: Path) -> None:
    packages, scripts = _wheel_ownership(wheel)
    assert packages == frozenset({"study_agent"})
    assert scripts == frozenset(HARNESS_SCRIPTS)
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        metadata = BytesParser().parsebytes(archive.read(metadata_name))
    requirements = metadata.get_all("Requires-Dist", [])
    assert all("extra ==" in requirement for requirement in requirements)


def _python(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _script(environment: Path, name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    directory = "Scripts" if os.name == "nt" else "bin"
    return environment / directory / f"{name}{suffix}"


def _clean_install(environment: Path, *artifacts: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        command = [
            str(_python(environment)),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-deps",
            *(str(item) for item in artifacts),
        ]
    else:
        subprocess.run(
            [uv, "venv", "--python", sys.executable, str(environment)],
            check=True,
            cwd=environment.parent,
            capture_output=True,
            text=True,
        )
        command = [
            uv,
            "pip",
            "install",
            "--python",
            str(_python(environment)),
            "--no-deps",
            *(str(item) for item in artifacts),
        ]
    subprocess.run(
        command,
        check=True,
        cwd=environment,
        env={
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONPATH", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"}
        },
        capture_output=True,
        text=True,
    )


def _build_sdist_artifact(sdist: Path, root: Path) -> Path:
    source_root = root / "source"
    source_root.mkdir(parents=True)
    with tarfile.open(sdist, "r:gz") as archive:
        archive.extractall(source_root, filter="data")
    project = next(path for path in source_root.iterdir() if path.is_dir())
    wheel_root = root / "wheel"
    wheel_root.mkdir()
    if importlib.util.find_spec("build") is not None:
        command = [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(wheel_root),
        ]
    else:
        uv = shutil.which("uv")
        if uv is None:
            pytest.fail("PF-09 sdist verification requires python-build or uv")
        command = [uv, "build", "--wheel", "--out-dir", str(wheel_root)]
    subprocess.run(
        command,
        check=True,
        cwd=project,
        capture_output=True,
        text=True,
    )
    return next(wheel_root.glob("*.whl"))


def test_positive_downstream_coinstalls_from_artifacts(tmp_path: Path) -> None:
    harness_wheel, harness_sdist = _artifacts()
    _assert_harness_ownership(harness_wheel)
    fixture_wheel = _build_fixture(
        FIXTURES / "synthetic-downstream-positive",
        tmp_path / "fixture-dist",
    )
    assert _wheel_ownership(fixture_wheel) == (
        frozenset({"cardine"}),
        frozenset({"cardine-synthetic"}),
    )
    _assert_collision_free(fixture_wheel)

    wheel_env = tmp_path / "wheel-env"
    _clean_install(wheel_env, harness_wheel, fixture_wheel)
    subprocess.run(
        [
            str(_python(wheel_env)),
            "-I",
            "-c",
            "import cardine,study_agent;"
            "assert cardine.VALUE=='cardine-only';"
            "assert study_agent.__version__=='0.2.0'",
        ],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    command = subprocess.run(
        [str(_script(wheel_env, "cardine-synthetic"))],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert command.stdout == "cardine-synthetic\n"
    subprocess.run(
        [str(_script(wheel_env, "study-agent")), "--help"],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    sdist_wheel = _build_sdist_artifact(harness_sdist, tmp_path / "sdist-build")
    sdist_env = tmp_path / "sdist-env"
    _clean_install(sdist_env, sdist_wheel)
    subprocess.run(
        [
            str(_python(sdist_env)),
            "-I",
            "-c",
            "import study_agent; assert study_agent.__version__=='0.2.0'",
        ],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )


def test_pre_adoption_fixture_is_rejected_before_install(tmp_path: Path) -> None:
    fixture_wheel = _build_fixture(
        FIXTURES / "cardine-pre-adoption-negative",
        tmp_path / "negative-dist",
    )
    with pytest.raises(RuntimeError, match="collides with Harness ownership"):
        _assert_collision_free(fixture_wheel)
