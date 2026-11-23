# The 100-App Buildability Map

Research pipeline and case study for the Composio **AI Product Ops Intern** take-home.

**Live case study →** https://amshu18.github.io/composio-app-research/

For each of 100 apps: what auth it uses, whether a developer can get credentials
themselves or has to ask a human, how broad the API surface is, and whether an
agent toolkit could be built today. Then the part that matters — the patterns
across all 100, and an honest account of how accurate the findings are.

---

## The headline

> Auth is almost never the blocker. **Access** is.

| | |
|---|---|
| Self-serve credentials | **79 / 100** (58 free, 21 paid plan) |
| Behind a review or sales gate | **19** |
| No public API at all | **2** |
| Buildable today | **74** · with caveats **18** · blocked **8** |
| Primary auth: API key vs OAuth2 | **50 vs 40** |
| Already shipped as a Composio toolkit | **80 / 100** (13,470 tools) |

The sharpest cut is by category. Developer Infra and Productivity are **100%**
self-serve. Marketing & Ads is **50%** — Google Ads, Meta Ads, LinkedIn Ads,
Pinterest and Threads each put a human review between you and a production
token. Those blockers are commercial, not technical, so they are solved by
outreach rather than engineering.

---

## Running it

Full prerequisites, API-key sources and costs, and the GitHub Pages steps are in
**[SETUP.md](SETUP.md)**. The short version:

```bash
pip install -r requirements.txt
```

```bash
python3 agent/run.py
```

That runs the whole pipeline except the LLM stage — catalog probe, both
verification loops, the human-audit scorer, the clustering and the page render —
and needs **no API key**. It takes about a minute and only talks to
`composio.dev`.

To also run the documentation-research stage:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python3 agent/run.py --research
```

Single stages, if you want to poke at one:

```bash
python3 agent/composio_catalog.py            # stage 2  — probe Composio's catalog
python3 agent/composio_api.py --selftest     # stage 2b — authenticated, needs COMPOSIO_API_KEY
python3 agent/research.py --only 5 17 94     # stage 3 — research three apps
python3 agent/verify.py                      # stage 4 — loops A and B
python3 agent/cluster.py                     # stage 5 — recompute every statistic
python3 site/build.py                        # stage 5 — re-render the page
```

---

## How it works

| Stage | What it does | Needs a key |
|---|---|---|
| 1 Seed | 100 apps × 10 categories → `data/apps.json` | no |
| 2 Catalog probe | async slug resolution against `composio.dev/toolkits/<slug>.md`; parses auth schemes, tool counts, triggers | no |
| 3 Doc research | Claude + server-side web search → one schema-valid `AppFinding` per app | **yes** |
| 4 Verify | parser regression with ground truth, cross-source agreement, human audit | no |
| 5 Cluster & render | deterministic counts → `patterns.json` → `site/index.html` | no |

**No model sits in the scoring path.** Claude reads documentation; every number
on the page is a `Counter` over `data/findings.json`. That is why the patterns
are reproducible from a clean checkout.

### Using Composio's own catalog as a second opinion

Stage 2 asks Composio's public catalog what it already knows about each app.
That gives three things at once: a buildability signal (a shipped toolkit is the
strongest possible evidence an app is buildable), a measure of API breadth (tool
count per toolkit), and — most usefully — an **independent** auth classification
to check the documentation pass against. That cross-check is Loop B below, and
it caught two real bugs.

---

## Verification

Three loops. Two have hard ground truth and show a measured first-pass to
second-pass gain.

**Loop A — parser regression.** Pass 1 matched auth keywords anywhere in a
toolkit page. Pass 2 reads only the documented `## Authentication` section and
its machine-readable `Type:` lines, which *are* the ground truth, so
precision and recall are directly computable over all 79 pages.

| | precision | recall | F1 |
|---|---|---|---|
| Pass 1 — keyword match | 0.739 | 0.936 | 0.826 |
| Pass 2 — structured parse | **1.000** | **1.000** | **1.000** |

Pass 1 invented 36 auth schemes that do not exist, across 30 pages. Telegram
came back with four schemes when it has one, because the prose mentions the
others. Recall was never the problem; confident fabrication was.

**Loop B — cross-source agreement.** Composio's classification vs. the vendor's
own docs, over 78 comparable rows: **96.2% → 98.7%**. Of three conflicts, two
(Plaid, higgsfield) were bugs in my own normaliser — it only recognised the
words "api key" and "token", so credential pairs like `client_id + secret`
normalised to nothing. One real conflict survives: **Consensus**, whose REST API
uses an API key while its MCP server uses OAuth 2.1. Both sources are right
about different surfaces.

**Loop C — human audit.** 20 of 100, stratified across evidence tier, with the
weakest tier deliberately over-sampled. 13 OK, 5 weak, **2 wrong** → 65% strict,
90% counting weak rows as acceptable.

| Evidence tier | Sampled | OK | Weak | Miss | Strict |
|---|---|---|---|---|---|
| `catalog` — re-fetched and machine-parsed | 5 | 5 | 0 | 0 | **100%** |
| `grounded` — researched this run | 10 | 7 | 3 | 0 | **70%** |
| `prior` — model knowledge + canonical URL | 5 | 1 | 2 | 2 | **20%** |

**Both misses came from the lowest-evidence tier**, which is the argument for
labelling provenance per row instead of quoting one accuracy number. The two
errors — Plaid misclassified as self-serve when production access is reviewed,
and a wrong note on Harvest's free plan — are corrected in the data and shown
on the page rather than quietly fixed.

---

## Where a human was needed

- **Slug resolution.** Composio's slugs are not derivable from app names
  (`Zoho CRM → zoho`, `Otter AI → otter_ai_mcp`). 41 of 100 needed a hand-written
  alias, kept in one audited dict in `agent/composio_catalog.py`.
- **Judging "gated".** No page says "we are partner-gated". You infer it from a
  *Request access* button, a missing price, or two help articles that contradict
  each other — Ahrefs publishes two that disagree about whether its API needs
  Enterprise. A classifier picks one; a human records the conflict.
- **Knowing when to stop.** For **iPayX**, every search returned a different
  company called iPay. The correct output is "not found", and the schema makes
  that expressible.

## What this does not prove

- The sandbox allowed egress to `composio.dev` and `github.com` only. Composio's
  catalog was fetched and parsed for real; vendor docs were reached through a
  search tool that returns primary URLs and quoted passages, so evidence links
  are real but most were not re-opened byte-for-byte at render time.
- 8 rows rest on model prior. They are labelled `prior` and are the first to
  re-check — the audit found both of its misses there.
- "Official MCP" (33 apps) is under-counted. Absence means *not found*, never
  *does not exist*.
- Gating moves fast. Google sunset Google Ads developer tokens on 2026-09-09 and
  moved access levels onto Cloud projects — after the model's training cutoff,
  caught only because the research pass ran.

---

## Layout

```
agent/
  composio_catalog.py   stage 2 — the catalog probe
  research.py           stage 3 — Claude + web search, structured output
  models.py             the AppFinding schema
  verify.py             stage 4 — loops A and B
  cluster.py            stage 5 — deterministic pattern analysis
  run.py                orchestrator
audit/
  human_audit.py        loop C — the 20-row stratified audit
data/
  apps.json             the 100-app research set
  findings_seed.py      the reviewed findings table, with provenance per row
  findings.json         merged output — one record per app
  composio_catalog.json raw probe output
  patterns.json         every statistic on the page
  verification.json     loop A and B results
  audit.json            loop C results
site/
  template.html         the page
  build.py              renders index.html + artifact.html from data/
docs/
  architecture.md       design decisions and the taxonomy
```

## Taxonomy

| Code | Meaning |
|---|---|
| `SS` | Self-serve, free tier or trial sufficient for a working key |
| `SSP` | Self-serve, but a paid plan is required first |
| `REV` | Self-registration, then an approval gate before production |
| `SALES` | Partnership, enterprise contract or booked call required |
| `NONE` | No public API to build against |

A free sandbox behind a reviewed production gate is `REV`, not `SS`. That rule
is what moved Plaid during the audit.
