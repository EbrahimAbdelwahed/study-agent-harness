from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"


def test_root_and_facade_import_without_runtime_side_effects() -> None:
    script = r'''
import asyncio
import builtins
import importlib.metadata
import io
import json
import os
import pathlib
import sqlite3

events = []


def blocked(label):
    def guard(*args, **kwargs):
        events.append(label)
        raise AssertionError(label)

    return guard


class GuardedEnvironment:
    def __init__(self, original):
        self._original = original

    def __getitem__(self, key):
        events.append("environment")
        return self._original[key]

    def __setitem__(self, key, value):
        events.append("environment")
        return self._original.__setitem__(key, value)

    def __delitem__(self, key):
        events.append("environment")
        return self._original.__delitem__(key)

    def __iter__(self):
        events.append("environment")
        return iter(self._original)

    def __len__(self):
        events.append("environment")
        return len(self._original)

    def __contains__(self, key):
        events.append("environment")
        return key in self._original

    def get(self, key, *default):
        events.append("environment")
        return self._original.get(key, *default)


os.environ = GuardedEnvironment(os.environ)
builtins.open = blocked("filesystem")
io.open = blocked("filesystem")
pathlib.Path.open = blocked("filesystem")
os.open = blocked("filesystem")
sqlite3.connect = blocked("database")
importlib.metadata.entry_points = blocked("plugin-registration")
for name in ("new_event_loop", "get_event_loop", "set_event_loop", "run"):
    setattr(asyncio, name, blocked("event-loop"))

import study_agent

version = study_agent.__version__
manifest = study_agent.api.public_manifest()
print(json.dumps({"events": events, "version": version, "fingerprint": manifest.fingerprint}))
'''
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
    result = json.loads(process.stdout)
    assert result["events"] == []
    assert result["version"]
    assert len(result["fingerprint"]) == 64
