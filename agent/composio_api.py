"""
Stage 2b: authenticated Composio catalog verification (optional).

Stage 2 (`composio_catalog.py`) reads Composio's PUBLIC toolkit pages and needs
no credentials. This stage asks the same questions through the authenticated
REST API, which returns the catalog's own structured fields instead of rendered
markdown:

    GET /api/v3.1/toolkits/{slug}   -> auth_config_details[].mode, toolkit_type,
                                       composio_managed_auth_schemes, enabled
    GET /api/v3.1/tools             -> tool inventory for a toolkit

`auth_config_details[].mode` is an enum (OAUTH2 / OAUTH1 / API_KEY / ...), so it
is a stronger signal than anything parsed out of a page, and it gives the
verification step a third independent source.

Requires COMPOSIO_API_KEY (project API key, `x-api-key` header).

    python3 agent/composio_api.py --selftest     # one toolkit, prints raw + parsed
    python3 agent/composio_api.py                # all 100

Field names below come from Composio's published v3.1 OpenAPI reference. The
build sandbox could not reach backend.composio.dev, so this stage has not been
executed against the live API — run --selftest first and it will tell you
immediately if a field has moved.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.env import load_env

load_env()

BASE = "https://backend.composio.dev/api/v3.1"

MODE_LABEL = {
    "OAUTH2": "OAuth2", "OAUTH1": "OAuth1", "OAUTH1A": "OAuth1",
    "API_KEY": "API key", "BEARER_TOKEN": "Bearer token", "BASIC": "Basic",
    "BASIC_WITH_JWT": "Basic+JWT", "NO_AUTH": "No auth",
    "GOOGLE_SERVICE_ACCOUNT": "Service account", "CALCOM_AUTH": "Vendor-specific",
    "BILLCOM_AUTH": "Vendor-specific", "SNOWFLAKE_AUTH": "Vendor-specific",
}


def parse_toolkit(doc: dict) -> dict:
    """Pull the fields we compare on. Tolerant: the API may add or move keys."""
    modes: list[str] = []
    for detail in doc.get("auth_config_details") or []:
        mode = (detail or {}).get("mode")
        if mode and mode not in modes:
            modes.append(mode)
    managed = doc.get("composio_managed_auth_schemes") or []
    for m in managed:
        up = str(m).upper()
        if up not in modes:
            modes.append(up)
    return {
        "slug": doc.get("slug"),
        "name": doc.get("name"),
        "type": doc.get("type"),                  # native | custom
        "toolkit_type": doc.get("toolkit_type"),  # api | mcp
        "enabled": doc.get("enabled"),
        "auth_modes_raw": modes,
        "auth_schemes": [MODE_LABEL.get(m, m) for m in modes],
        "composio_managed_auth_schemes": managed,
        "has_managed_auth": bool(doc.get("composio_managed_auth")),
    }


async def get_toolkit(client: httpx.AsyncClient, slug: str, sem: asyncio.Semaphore) -> dict:
    async with sem:
        try:
            r = await client.get(f"{BASE}/toolkits/{slug}", timeout=30.0)
        except httpx.HTTPError as exc:
            return {"slug": slug, "error": repr(exc)}
    if r.status_code == 404:
        return {"slug": slug, "found": False}
    if r.status_code == 401:
        return {"slug": slug, "error": "401 - check COMPOSIO_API_KEY"}
    if r.status_code != 200:
        return {"slug": slug, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
    return {"found": True, **parse_toolkit(r.json())}


async def run(slugs: list[str], key: str, concurrency: int = 6) -> list[dict]:
    headers = {"x-api-key": key, "accept": "application/json",
               "user-agent": "composio-app-research/1.0"}
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        return await asyncio.gather(*(get_toolkit(client, s, sem) for s in slugs))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true",
                    help="fetch one toolkit, print the raw JSON and the parsed view")
    ap.add_argument("--concurrency", type=int, default=6)
    args = ap.parse_args()

    key = os.environ.get("COMPOSIO_API_KEY")
    if not key:
        sys.exit("COMPOSIO_API_KEY is not set. Get a project API key from "
                 "https://platform.composio.dev -> Settings -> API Keys. This stage is "
                 "optional; agent/composio_catalog.py covers the same ground without a key.")

    if args.selftest:
        headers = {"x-api-key": key, "accept": "application/json"}
        r = httpx.get(f"{BASE}/toolkits/github", headers=headers, timeout=30.0)
        print(f"HTTP {r.status_code}")
        if r.status_code != 200:
            sys.exit(r.text[:800])
        doc = r.json()
        print("\ntop-level keys returned:\n ", sorted(doc.keys()))
        print("\nparsed:\n", json.dumps(parse_toolkit(doc), indent=2))
        missing = [k for k in ("slug", "auth_config_details", "toolkit_type")
                   if k not in doc]
        print("\nMISSING EXPECTED KEYS:", missing or "none — shape matches the reference")
        return

    catalog = json.loads((ROOT / "data" / "composio_catalog.json").read_text())
    slugs = [r["slug"] for r in catalog if r["found"]]
    rows = asyncio.run(run(slugs, key, args.concurrency))

    out = ROOT / "data" / "composio_api.json"
    out.write_text(json.dumps(rows, indent=2))

    ok = [r for r in rows if r.get("found")]
    errs = [r for r in rows if r.get("error")]
    print(f"queried {len(rows)} toolkits -> {len(ok)} ok, {len(errs)} errors")
    for e in errs[:5]:
        print("  ", e["slug"], e["error"][:100])

    # third cross-source check: public page vs authenticated API
    by_slug = {r["slug"]: r for r in ok}
    agree = disagree = 0
    for c in catalog:
        if not c["found"] or c["slug"] not in by_slug:
            continue
        pub = {s.lower() for s in c["auth_schemes"]}
        api = {s.lower() for s in by_slug[c["slug"]]["auth_schemes"]}
        if not pub or not api:
            continue
        if pub & api:
            agree += 1
        else:
            disagree += 1
            print(f"   conflict {c['slug']}: page={sorted(pub)} api={sorted(api)}")
    total = agree + disagree
    if total:
        print(f"page-vs-API agreement: {agree}/{total} = {agree / total:.1%}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
