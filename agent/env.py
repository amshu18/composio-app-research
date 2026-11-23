"""
Minimal .env loader.

The pipeline reads credentials from the environment. Exporting them by hand is
one of the easiest things to get wrong - the incantation differs between bash,
zsh, PowerShell and cmd.exe, and a silent failure there looks exactly like a
bad API key. So the entry points call load_env() and read a .env file in the
repo root directly.

No dependency, and deliberately conservative:
  - a real environment variable always wins over the file
  - blank values in the file are ignored, so the shipped .env.example template
    does not mask a key that is already exported
  - `export FOO=bar` and surrounding quotes are both tolerated
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path | None = None) -> list[str]:
    """Load .env into os.environ. Returns the names actually set."""
    env_path = path or (ROOT / ".env")
    if not env_path.exists():
        return []
    loaded: list[str] = []
    for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or not value:
            continue
        if os.environ.get(key):      # a real export wins
            continue
        os.environ[key] = value
        loaded.append(key)
    return loaded
