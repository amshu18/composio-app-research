"""
Stage 3: documentation research.

For each app, a model researches the vendor's own documentation with web search
and returns one schema-valid AppFinding. Two backends are supported and produce
the same records:

    --provider anthropic   Claude + server-side web search (one call per app)
    --provider gemini      Gemini + Google Search grounding (two calls per app)

With no --provider, whichever key is set wins. See agent/providers.py for why
the Gemini path splits into two calls.

This is the only stage that needs a model key. Everything else in the repo
reproduces from a clean checkout with no credentials:

    python3 agent/run.py

Examples:

    python3 agent/research.py --list-models          # what can this key see?
    python3 agent/research.py --only 5 17 94         # three apps, costs cents
    python3 agent/research.py                        # all 100
    python3 agent/research.py --provider gemini --model gemini-3.8-flash
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent import providers  # noqa: E402
from agent.env import load_env  # noqa: E402

load_env()

OUT = ROOT / "data" / "research_raw.jsonl"


async def one(provider, sem: asyncio.Semaphore, app: dict) -> dict:
    payload = {"name": app["name"], "category": app["category"], "hint": app["hint"]}
    async with sem:
        for attempt in range(3):
            try:
                finding = await provider.research(payload)
            except Exception as exc:  # noqa: BLE001 - retry any transient failure
                if attempt == 2:
                    return {"id": app["id"], "name": app["name"], "error": repr(exc)[:400]}
                await asyncio.sleep(2 ** attempt * 3)
                continue
            return {"id": app["id"], "provider": provider.name,
                    "model": provider.model, **finding.model_dump()}
    return {"id": app["id"], "name": app["name"], "error": "unreachable"}


async def main_async(args) -> None:
    provider = providers.build(args.provider, args.model)
    print(f"provider={provider.name}  model={provider.model}")

    apps = json.loads((ROOT / "data" / "apps.json").read_text())["apps"]
    if args.only:
        wanted = set(args.only)
        apps = [a for a in apps if a["id"] in wanted]
    print(f"researching {len(apps)} app(s) at concurrency {args.concurrency}\n")

    sem = asyncio.Semaphore(args.concurrency)
    results = await asyncio.gather(*(one(provider, sem, a) for a in apps))

    with OUT.open("w") as fh:
        for r in results:
            fh.write(json.dumps(r) + "\n")

    ok = [r for r in results if "error" not in r]
    print(f"\nresearched {len(ok)}/{len(results)} apps -> {OUT}")
    for r in results:
        if "error" in r:
            print("  FAILED", r["name"], "-", r["error"][:140])
    if ok:
        from collections import Counter
        print("  access split:", dict(Counter(r["access"] for r in ok)))
        low = [r["name"] for r in ok if r["confidence"] == "low"]
        if low:
            print("  low confidence (check these by hand):", ", ".join(low))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", choices=["anthropic", "gemini"],
                    help="default: whichever API key is set")
    ap.add_argument("--model", help="override the model id")
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--only", nargs="*", type=int, metavar="ID",
                    help="research only these app ids (1-100)")
    ap.add_argument("--list-models", action="store_true",
                    help="print the models this key can use, then exit")
    args = ap.parse_args()

    try:
        _run(args)
    except RuntimeError as exc:
        sys.exit(f"error: {exc}")


def _run(args) -> None:
    if args.list_models:
        p = providers.build(args.provider, args.model)
        if hasattr(p, "available_models"):
            print(f"{p.name} models visible to this key:")
            for m in sorted(p.available_models()):
                print("  ", m)
            print(f"\nwould use: {p.model}")
        else:
            print(f"{p.name}: model listing not implemented; would use {p.model}")
        return

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
