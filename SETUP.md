# Setup

Two ways to use this: **view the case study** (no install, no keys) or **run the
research pipeline** (Python, optional keys).

---

## 1. Just view the case study

**Hosted:** https://amshu18.github.io/composio-app-research/

**Locally**, after cloning — `index.html` is fully self-contained, so opening the
file works:

```bash
git clone https://github.com/amshu18/composio-app-research.git
```

```bash
cd composio-app-research && python3 -m http.server 8000
```

Then open http://localhost:8000. (Double-clicking `index.html` also works; the
local server only matters if you want the same origin behaviour as the hosted
copy.)

---

## 2. Run the pipeline

### Prerequisites

| Thing | Version | Check |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| pip | any | `python3 -m pip --version` |

```bash
python3 -m venv .venv && source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

### Run everything that needs no credentials

```bash
python3 agent/run.py
```

About a minute. Only talks to `composio.dev`. This runs:

| Stage | What it does |
|---|---|
| 2 Catalog probe | Resolves 100 apps against Composio's public toolkit pages |
| 4 Verify | Loop A parser regression, Loop B cross-source agreement |
| 4c Audit | Scores the 20-row hand audit |
| 5 Cluster | Recomputes every statistic into `patterns.json` |
| 5 Render | Rebuilds `index.html` from the data |

If the numbers in `data/patterns.json` match what the page shows, the whole
analysis reproduced from scratch.

---

## 3. API keys

**You need none of these to reproduce the published results.** Each one unlocks
an extra stage.

Stage 3 takes **either** an Anthropic key **or** a Gemini key. Pick one.

### Option A — `GEMINI_API_KEY`

| | |
|---|---|
| Where | https://aistudio.google.com/apikey (`GOOGLE_API_KEY` also works) |
| Install | `pip install google-genai` |
| Cost | Gemini has a free tier with daily quota; 100 apps x 2 calls usually fits or costs well under a dollar |

Gemini's Google Search grounding and `response_schema` do not reliably combine
— the API has rejected the pair outright, and where it is allowed, grounding
metadata comes back empty. So the Gemini path makes **two** calls per app:
a grounded research call, then a structuring call with the schema enforced.
Source URLs come from the grounding metadata, not from the model's prose.

Check what your key can see first — Google's model IDs change often, and the
code picks the best available rather than hardcoding one:

```bash
export GEMINI_API_KEY=...
```

```bash
python3 agent/research.py --list-models
```

Then try three apps before spending on all 100:

```bash
python3 agent/research.py --only 5 17 94
```

```bash
python3 agent/run.py --research
```

### Option B — `ANTHROPIC_API_KEY`

| | |
|---|---|
| Where | https://platform.claude.com -> **API keys** -> *Create key* |
| Install | `pip install anthropic` |
| Format | `sk-ant-...` |
| Cost | ~**$3-8** for all 100 on `claude-opus-5-5`; `--model claude-sonnet-5-5` is roughly a quarter of that |
| Billing | Pay-as-you-go — add credit in the Console first or requests 400 |

One call per app: server-side web search and structured output compose, so the
model researches and emits schema-valid JSON in a single turn.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

```bash
python3 agent/research.py --only 5 17 94
```

With both keys set, Anthropic wins. Force the other with
`--provider gemini`.

### `COMPOSIO_API_KEY` — unlocks stage 2b (authenticated catalog check)

| | |
|---|---|
| Where | https://platform.composio.dev → **Settings** → *API Keys* |
| Header | sent as `x-api-key` |
| Unlocks | `agent/composio_api.py` — re-checks the catalog through Composio's REST **v3.1** API instead of its public pages, giving a third independent auth source |
| Cost | Free tier is sufficient; these are catalog reads, not tool executions |

Run the self-test first. It fetches one toolkit and tells you whether the
response shape still matches what the code expects:

```bash
export COMPOSIO_API_KEY=...
```

```bash
python3 agent/composio_api.py --selftest
```

If it prints `MISSING EXPECTED KEYS: none`, run the full stage:

```bash
python3 agent/run.py --composio-api
```

> This stage was written against Composio's published v3.1 OpenAPI reference but
> could **not** be executed during the build — the sandbox could not reach
> `backend.composio.dev`. The self-test exists precisely so the first real run
> tells you if a field has moved. Stage 2, which produced the shipped data,
> needs no key and was fully exercised.

### Keys you do **not** need

OpenAI, Firecrawl, Tavily, Exa, or accounts with any of the 100 apps. The
assignment explicitly does not require paid accounts, and recording an app as
gated *is* the finding.

### Using a `.env` file instead of exports

```bash
cp .env.example .env
```

Fill it in, then `set -a && source .env && set +a`. `.env` is gitignored —
never commit it.

---

## 4. Publishing the page

If you are running this under a **different GitHub account**, repoint it first —
this rewrites the footer link, the README and SETUP.md, then rebuilds the page:

```bash
python3 scripts/set_owner.py YOUR-GITHUB-USERNAME
```

GitHub Pages serves `index.html` from the repository root.

1. **github.com/amshu18/composio-app-research/settings/pages**
2. **Source** → *Deploy from a branch*
3. **Branch** → `main`, folder → `/ (root)` → **Save**

First build takes 1–2 minutes, then the page is live at
`https://amshu18.github.io/composio-app-research/`.

To update it after changing the data:

```bash
python3 agent/run.py && git add -A && git commit -m "Refresh findings" && git push
```

---

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: httpx` | deps not installed | `pip install -r requirements.txt` |
| Stage 2 finds 0 toolkits | no egress to `composio.dev` | check proxy/firewall; the probe needs that one host |
| `No model key found` | only stage 3 needs a key | run `python3 agent/run.py` without `--research` |
| `could not list Gemini models` | bad or unset `GEMINI_API_KEY` | regenerate at aistudio.google.com/apikey |
| Gemini returns schema errors | model ignored the schema | `--list-models`, then pin a different one with `--model` |
| `401 - check COMPOSIO_API_KEY` | wrong or expired key | regenerate in the Composio dashboard |
| Stage 3 reports `schema:` errors | model returned off-schema JSON | re-run those ids with `--only`; the row is skipped, not corrupted |
| Pages shows a 404 | source not set to root | Settings → Pages → branch `main`, folder `/ (root)` |
| Page renders unstyled | Google Fonts blocked | cosmetic only; the fallback stack still reads correctly |
