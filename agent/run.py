"""
Orchestrator. Runs the pipeline end to end.

    python3 agent/run.py              # everything that needs no API key
    python3 agent/run.py --research   # also run the LLM documentation pass

Stages 1, 2, 4 and 5 are deterministic and reproducible with no credentials.
Stage 3 is the only one that calls a model.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.env import load_env  # noqa: E402

loaded = load_env()

STAGES = [
    ("2  catalog probe", [sys.executable, "agent/composio_catalog.py"]),
    ("4  verification", [sys.executable, "agent/verify.py"]),
    ("4c human audit", [sys.executable, "audit/human_audit.py"]),
    ("5  cluster", [sys.executable, "agent/cluster.py"]),
    ("5  render", [sys.executable, "site/build.py"]),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--research", action="store_true",
                    help="also run stage 3 (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--composio-api", action="store_true",
                    help="also run stage 2b, the authenticated catalog check "
                         "(needs COMPOSIO_API_KEY)")
    args = ap.parse_args()

    stages = list(STAGES)
    if args.composio_api:
        stages.insert(1, ("2b authenticated catalog", [sys.executable, "agent/composio_api.py"]))
    if args.research:
        stages.insert(1, ("3  doc research", [sys.executable, "agent/research.py"]))

    if loaded:
        print("loaded from .env:", ", ".join(loaded))

    for name, cmd in stages:
        print(f"\n\033[1m── stage {name} ─────────────────────────\033[0m")
        r = subprocess.run(cmd, cwd=ROOT)
        if r.returncode != 0:
            sys.exit(f"stage {name} failed with exit code {r.returncode}")
    print("\npipeline complete — open index.html")


if __name__ == "__main__":
    main()
