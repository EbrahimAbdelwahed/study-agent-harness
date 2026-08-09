#!/usr/bin/env python3
"""Dispatch isolated Codex CLI lanes coordinated through Agent Mail.

The dispatcher is intentionally conservative:

* dry-run is the default;
* every worker gets a separate Git worktree and branch;
* reservation surfaces may not overlap within one Agent Mail project;
* Beads remains the task-status authority;
* workers commit to their lane branch but never merge or close the bead.

Agent Mail is used through its local ``am`` CLI. A persistent HTTP service or
global Codex MCP configuration is therefore optional, not a prerequisite.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MODEL = "gpt-5.6-luna"
REASONING_EFFORT = "xhigh"
DEFAULT_CODEX = "/Applications/ChatGPT.app/Contents/Resources/codex"
SAFE_WORKTREE_PARENT = Path("/private/tmp/agent-mail-swarm")
AGENT_NAME_RE = re.compile(r"^[A-Z][a-z]+[A-Z][a-z]+$")
LANE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ManifestError(ValueError):
    """Raised when a lane manifest is unsafe or incomplete."""


@dataclass(frozen=True)
class Lane:
    lane_id: str
    agent_name: str
    repo: Path
    project_key: Path
    base_ref: str
    beads_db: Path
    bead_id: str
    brief: str
    reserve_paths: tuple[str, ...]
    forbidden_paths: tuple[str, ...]
    verification: tuple[str, ...]


@dataclass(frozen=True)
class Manifest:
    run_id: str
    orchestrator_agent: str
    worktree_root: Path
    state_dir: Path
    max_workers: int
    lanes: tuple[Lane, ...]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestError(f"cannot read manifest {path}: {error}") from error
    if not isinstance(value, dict):
        raise ManifestError("manifest root must be a JSON object")
    return value


def _required_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{field} must be a non-empty string")
    return value.strip()


def _absolute_path(value: Any, field: str) -> Path:
    raw = _required_str(value, field)
    path = Path(raw)
    if not path.is_absolute():
        raise ManifestError(f"{field} must be absolute: {raw}")
    return path.resolve(strict=False)


def _string_tuple(value: Any, field: str, *, required: bool = False) -> tuple[str, ...]:
    if value is None and not required:
        return ()
    if not isinstance(value, list):
        raise ManifestError(f"{field} must be an array of strings")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(_required_str(item, f"{field}[{index}]").replace("\\", "/"))
    if required and not result:
        raise ManifestError(f"{field} must not be empty")
    return tuple(result)


def _reservation_prefix(pattern: str) -> str:
    prefix = re.split(r"[*?[]", pattern, maxsplit=1)[0].rstrip("/")
    return prefix or "."


def _patterns_overlap(left: str, right: str) -> bool:
    left_prefix = _reservation_prefix(left)
    right_prefix = _reservation_prefix(right)
    return (
        left_prefix == right_prefix
        or left_prefix.startswith(f"{right_prefix}/")
        or right_prefix.startswith(f"{left_prefix}/")
    )


def _validate_worktree_root(path: Path) -> None:
    if path in {Path("/"), Path.home(), Path("/private/tmp")}:
        raise ManifestError(f"unsafe worktree_root: {path}")
    try:
        path.relative_to(SAFE_WORKTREE_PARENT)
    except ValueError as error:
        raise ManifestError(
            f"worktree_root must be below {SAFE_WORKTREE_PARENT}: {path}"
        ) from error


def parse_manifest(path: Path) -> Manifest:
    raw = _load_json(path)
    run_id = _required_str(raw.get("run_id"), "run_id")
    if not LANE_ID_RE.fullmatch(run_id):
        raise ManifestError("run_id must contain lowercase letters, digits, and hyphens")
    orchestrator = _required_str(raw.get("orchestrator_agent"), "orchestrator_agent")
    if not AGENT_NAME_RE.fullmatch(orchestrator):
        raise ManifestError("orchestrator_agent must look like BlueLake")
    worktree_root = _absolute_path(raw.get("worktree_root"), "worktree_root")
    _validate_worktree_root(worktree_root)
    state_dir = _absolute_path(raw.get("state_dir"), "state_dir")
    max_workers = raw.get("max_workers", 8)
    if not isinstance(max_workers, int) or not 1 <= max_workers <= 32:
        raise ManifestError("max_workers must be an integer from 1 to 32")
    raw_lanes = raw.get("lanes")
    if not isinstance(raw_lanes, list):
        raise ManifestError("lanes must be an array")

    lanes: list[Lane] = []
    seen_ids: set[str] = set()
    seen_agents: set[tuple[Path, str]] = set()
    for index, item in enumerate(raw_lanes):
        if not isinstance(item, dict):
            raise ManifestError(f"lanes[{index}] must be an object")
        if item.get("enabled", True) is False:
            continue
        lane_id = _required_str(item.get("id"), f"lanes[{index}].id")
        if not LANE_ID_RE.fullmatch(lane_id):
            raise ManifestError(f"invalid lane id: {lane_id}")
        if lane_id in seen_ids:
            raise ManifestError(f"duplicate lane id: {lane_id}")
        seen_ids.add(lane_id)
        agent_name = _required_str(item.get("agent_name"), f"lanes[{index}].agent_name")
        if not AGENT_NAME_RE.fullmatch(agent_name):
            raise ManifestError(f"agent name must look like BlueLake: {agent_name}")
        project_key = _absolute_path(item.get("project_key"), f"lanes[{index}].project_key")
        agent_key = (project_key, agent_name)
        if agent_key in seen_agents:
            raise ManifestError(f"duplicate agent {agent_name} in {project_key}")
        seen_agents.add(agent_key)
        lane = Lane(
            lane_id=lane_id,
            agent_name=agent_name,
            repo=_absolute_path(item.get("repo"), f"lanes[{index}].repo"),
            project_key=project_key,
            base_ref=_required_str(item.get("base_ref"), f"lanes[{index}].base_ref"),
            beads_db=_absolute_path(item.get("beads_db"), f"lanes[{index}].beads_db"),
            bead_id=_required_str(item.get("bead_id"), f"lanes[{index}].bead_id"),
            brief=_required_str(item.get("brief"), f"lanes[{index}].brief"),
            reserve_paths=_string_tuple(
                item.get("reserve_paths"), f"lanes[{index}].reserve_paths", required=True
            ),
            forbidden_paths=_string_tuple(
                item.get("forbidden_paths"), f"lanes[{index}].forbidden_paths"
            ),
            verification=_string_tuple(
                item.get("verification"), f"lanes[{index}].verification", required=True
            ),
        )
        lanes.append(lane)

    if len(lanes) > max_workers:
        raise ManifestError(
            f"{len(lanes)} enabled lanes exceed max_workers={max_workers}; split the wave"
        )
    for index, left in enumerate(lanes):
        for right in lanes[index + 1 :]:
            if left.project_key != right.project_key:
                continue
            for left_path in left.reserve_paths:
                for right_path in right.reserve_paths:
                    if _patterns_overlap(left_path, right_path):
                        raise ManifestError(
                            "overlapping reservations in project "
                            f"{left.project_key}: {left.lane_id}:{left_path} and "
                            f"{right.lane_id}:{right_path}"
                        )
    return Manifest(
        run_id=run_id,
        orchestrator_agent=orchestrator,
        worktree_root=worktree_root,
        state_dir=state_dir,
        max_workers=max_workers,
        lanes=tuple(lanes),
    )


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )


def _require_executable(name: str, fallback: str | None = None) -> str:
    resolved = shutil.which(name)
    if resolved:
        return resolved
    if fallback and Path(fallback).is_file():
        return fallback
    raise ManifestError(f"required executable is unavailable: {name}")


def _branch_name(run_id: str, lane_id: str) -> str:
    return f"codex/mail-{run_id}-{lane_id}"


def _worktree_path(manifest: Manifest, lane: Lane) -> Path:
    return manifest.worktree_root / manifest.run_id / lane.lane_id


def _verify_lane_inputs(lane: Lane) -> None:
    if not (lane.repo / ".git").exists():
        raise ManifestError(f"lane repo is not a Git worktree: {lane.repo}")
    if not lane.beads_db.is_file():
        raise ManifestError(f"Beads database does not exist: {lane.beads_db}")
    if not (lane.repo / lane.brief).is_file():
        raise ManifestError(f"worker brief does not exist: {lane.repo / lane.brief}")


def _verify_ready_beads(br: str, lanes: tuple[Lane, ...]) -> None:
    """Reject lanes whose Beads task is not dependency-ready."""

    ready_by_db: dict[Path, set[str]] = {}
    for lane in lanes:
        ready = ready_by_db.get(lane.beads_db)
        if ready is None:
            result = _run([br, "--db", str(lane.beads_db), "ready", "--json"])
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError as error:
                raise ManifestError(
                    f"Beads ready output is not JSON for {lane.beads_db}: {error}"
                ) from error
            if not isinstance(payload, list):
                raise ManifestError(f"Beads ready output must be an array: {lane.beads_db}")
            ready = {
                item["id"]
                for item in payload
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }
            ready_by_db[lane.beads_db] = ready
        if lane.bead_id not in ready:
            raise ManifestError(
                f"bead is not dependency-ready in {lane.beads_db}: {lane.bead_id}"
            )


def render_plan(manifest: Manifest) -> str:
    lines = [
        f"run={manifest.run_id} lanes={len(manifest.lanes)} max={manifest.max_workers}",
        f"worktree_root={manifest.worktree_root}",
        f"state_dir={manifest.state_dir}",
    ]
    for lane in manifest.lanes:
        lines.extend(
            [
                "",
                f"[{lane.lane_id}] agent={lane.agent_name} bead={lane.bead_id}",
                f"  repo={lane.repo}",
                f"  base={lane.base_ref}",
                f"  branch={_branch_name(manifest.run_id, lane.lane_id)}",
                f"  worktree={_worktree_path(manifest, lane)}",
                f"  reserve={', '.join(lane.reserve_paths)}",
            ]
        )
    return "\n".join(lines)


def _worker_prompt(manifest: Manifest, lane: Lane, worktree: Path) -> str:
    allowed = "\n".join(f"- {path}" for path in lane.reserve_paths)
    forbidden = "\n".join(f"- {path}" for path in lane.forbidden_paths) or "- Everything else"
    verification = "\n".join(f"- {command}" for command in lane.verification)
    return f"""You are {lane.agent_name}, an external Codex implementation lane.

Goal: complete lane {lane.lane_id} for bead {lane.bead_id} within the exact
contract in {lane.brief}. You are not alone in the codebase. Do not delegate.

Coordination contract:
1. Read AGENTS.md, dev/index.md, the relevant handoff/spec, and {lane.brief}.
2. Inspect the bead with:
   br --db {lane.beads_db} show {lane.bead_id}
3. Your Agent Mail identity and exclusive reservations are already active.
   Use project {lane.project_key}, agent {lane.agent_name}, and thread
   {lane.bead_id}. Check inbox before editing:
   am inbox --project {lane.project_key} --agent {lane.agent_name}
4. Beads is status authority. Do not close the bead. Do not merge branches.
5. Commit only your owned paths to branch {_branch_name(manifest.run_id, lane.lane_id)}.

Allowed edit surface:
{allowed}

Forbidden edit surface:
{forbidden}

Required verification:
{verification}

On success, send the orchestrator a completion message with commit SHA,
changed files, exact test outcomes, and residual risks:
  am macros contact-handshake --project {lane.project_key} \\
    --from {lane.agent_name} --to {manifest.orchestrator_agent} \\
    --auto-accept --thread-id {lane.bead_id} \\
    --welcome-subject '[{lane.bead_id}] lane {lane.lane_id} complete' \\
    --welcome-body '<summary>' --json
Then release your reservations:
  am file_reservations release {lane.project_key} {lane.agent_name}

If blocked, send the blocker in the same thread and leave the reservation in
place only when another writer must not proceed. Worktree: {worktree}
"""


def _register_agent(am: str, project: Path, name: str, task: str) -> None:
    del task
    _run(
        [
            am,
            "agent",
            "start",
            "--project",
            str(project),
            "--agent",
            name,
            "--program",
            "codex-cli",
            "--model",
            MODEL,
            "--fix",
            "--json",
        ]
    )


def _reserve(am: str, lane: Lane) -> None:
    command = [
        am,
        "macros",
        "file-reservation-cycle",
        "--project",
        str(lane.project_key),
        "--agent",
        lane.agent_name,
    ]
    for path in lane.reserve_paths:
        command.extend(["--path", path])
    command.extend(
        [
            "--ttl",
            "14400",
            "--exclusive",
            "--reason",
            lane.bead_id,
            "--json",
        ]
    )
    _run(command)


def _send_assignment(am: str, manifest: Manifest, lane: Lane) -> None:
    body = (
        f"External lane `{lane.lane_id}` assigned on `{lane.base_ref}`. "
        f"Reserved: {', '.join(lane.reserve_paths)}. Read `{lane.brief}`."
    )
    _run(
        [
            am,
            "macros",
            "contact-handshake",
            "--project",
            str(lane.project_key),
            "--from",
            manifest.orchestrator_agent,
            "--to",
            lane.agent_name,
            "--auto-accept",
            "--thread-id",
            lane.bead_id,
            "--welcome-subject",
            f"[{lane.bead_id}] Start lane {lane.lane_id}",
            "--welcome-body",
            body,
            "--json",
        ]
    )


def _claim_bead(br: str, manifest: Manifest, lane: Lane) -> None:
    _run(
        [
            br,
            "--db",
            str(lane.beads_db),
            "update",
            lane.bead_id,
            "--status",
            "in_progress",
            "--assignee",
            lane.agent_name,
            "--actor",
            manifest.orchestrator_agent,
        ]
    )


def dispatch(manifest: Manifest, *, execute: bool) -> int:
    for lane in manifest.lanes:
        _verify_lane_inputs(lane)
    br = _require_executable("br") if manifest.lanes else "br"
    _verify_ready_beads(br, manifest.lanes)
    print(render_plan(manifest))
    if not execute:
        print("\nDry run only. Re-run with --execute to create worktrees and launch workers.")
        return 0

    git = _require_executable("git")
    am = _require_executable("am")
    codex = _require_executable("codex", DEFAULT_CODEX)
    manifest.worktree_root.joinpath(manifest.run_id).mkdir(parents=True, exist_ok=True)
    run_state_dir = manifest.state_dir / manifest.run_id
    run_state_dir.mkdir(parents=True, exist_ok=True)

    projects = {lane.project_key for lane in manifest.lanes}
    for project in projects:
        _register_agent(am, project, manifest.orchestrator_agent, f"orchestrate {manifest.run_id}")

    state: dict[str, Any] = {"run_id": manifest.run_id, "lanes": {}}
    for lane in manifest.lanes:
        worktree = _worktree_path(manifest, lane)
        if worktree.exists():
            raise ManifestError(f"refusing existing worktree target: {worktree}")
        branch = _branch_name(manifest.run_id, lane.lane_id)
        _run(
            [
                git,
                "-C",
                str(lane.repo),
                "worktree",
                "add",
                "-b",
                branch,
                str(worktree),
                lane.base_ref,
            ]
        )
        _register_agent(am, lane.project_key, lane.agent_name, f"{lane.bead_id}: {lane.lane_id}")
        _reserve(am, lane)
        _claim_bead(br, manifest, lane)
        _send_assignment(am, manifest, lane)

        log_path = run_state_dir / f"{lane.lane_id}.jsonl"
        last_path = run_state_dir / f"{lane.lane_id}.last.md"
        prompt = _worker_prompt(manifest, lane, worktree)
        log_handle = log_path.open("ab", buffering=0)
        process = subprocess.Popen(
            [
                codex,
                "exec",
                "--model",
                MODEL,
                "--config",
                f'model_reasoning_effort="{REASONING_EFFORT}"',
                "--sandbox",
                "workspace-write",
                "--approve-for-me",
                "--cd",
                str(worktree),
                "--json",
                "--output-last-message",
                str(last_path),
                "-",
            ],
            stdin=subprocess.PIPE,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env={**os.environ, "AGENT_NAME": lane.agent_name},
            start_new_session=True,
        )
        if process.stdin is None:
            raise RuntimeError("Codex worker stdin was not created")
        process.stdin.write(prompt.encode("utf-8"))
        process.stdin.close()
        state["lanes"][lane.lane_id] = {
            "agent": lane.agent_name,
            "bead": lane.bead_id,
            "pid": process.pid,
            "branch": branch,
            "worktree": str(worktree),
            "log": str(log_path),
            "last_message": str(last_path),
        }
        print(f"launched {lane.lane_id}: pid={process.pid} agent={lane.agent_name}")

    state_path = run_state_dir / "state.json"
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"state={state_path}")
    return 0


def status(manifest: Manifest) -> int:
    state_path = manifest.state_dir / manifest.run_id / "state.json"
    if not state_path.is_file():
        raise ManifestError(f"run state does not exist: {state_path}")
    state = _load_json(state_path)
    lanes = state.get("lanes")
    if not isinstance(lanes, dict):
        raise ManifestError("state lanes must be an object")
    for lane_id, raw in sorted(lanes.items()):
        if not isinstance(raw, dict) or not isinstance(raw.get("pid"), int):
            raise ManifestError(f"invalid state for lane {lane_id}")
        pid = raw["pid"]
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            process_state = "finished"
        except PermissionError:
            process_state = "running-uninspectable"
        else:
            process_state = "running"
        print(
            f"{lane_id}: {process_state} pid={pid} agent={raw.get('agent')} "
            f"bead={raw.get('bead')} log={raw.get('log')}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="validate and print a manifest")
    validate_parser.add_argument("manifest", type=Path)
    dispatch_parser = subparsers.add_parser("dispatch", help="plan or execute a swarm wave")
    dispatch_parser.add_argument("manifest", type=Path)
    dispatch_parser.add_argument(
        "--execute",
        action="store_true",
        help="create worktrees, reservations, mail threads, and Codex processes",
    )
    status_parser = subparsers.add_parser("status", help="show locally recorded worker PIDs")
    status_parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = parse_manifest(args.manifest.resolve())
        if args.command == "validate":
            print(render_plan(manifest))
            return 0
        if args.command == "dispatch":
            return dispatch(manifest, execute=args.execute)
        if args.command == "status":
            return status(manifest)
        raise AssertionError(f"unknown command: {args.command}")
    except (ManifestError, subprocess.CalledProcessError, OSError) as error:
        print(f"agent-mail-swarm: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
