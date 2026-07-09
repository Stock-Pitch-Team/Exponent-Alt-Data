# Exponent (EXPO) Alternative-Data Research Platform

Six independent data pipelines that test the EXPO buy thesis with **real, public,
primary-source data only** — no mock, simulated, or estimated numbers anywhere —
plus a static interactive dashboard for presenting the results.

## Quickstart

```powershell
# one-time setup
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env   # then fill in keys (see below)

# run pipelines (each is independent; safe to re-run — responses are cached)
.venv\Scripts\python scripts\run_pipeline.py p4   # OpenAlex moat graph (~1 min)
.venv\Scripts\python scripts\run_pipeline.py p6   # client R&D + EXPO financials (~2 min)
.venv\Scripts\python scripts\run_pipeline.py p3   # reactive demand index (~8 min, downloads ~380MB NHTSA files)
.venv\Scripts\python scripts\run_pipeline.py p5   # USAspending + Regulations.gov (~15 min)
.venv\Scripts\python scripts\run_pipeline.py p1   # headcount tracker (~3 min)
.venv\Scripts\python scripts\run_pipeline.py p2   # CourtListener (slow drip, see below)

# rebuild the dashboard data + QA
.venv\Scripts\python scripts\build_site_data.py
.venv\Scripts\python scripts\lint_outputs.py
.venv\Scripts\python scripts\build_single_file.py   # -> EXPO-dashboard.html

# view / share the dashboard
start EXPO-dashboard.html      # ONE self-contained file - email it, USB it, open anywhere
# dev version: .venv\Scripts\python -m http.server 8321 --directory site
```

## .env keys

| Key | Needed for | Where to get it |
|---|---|---|
| `REGULATIONS_GOV_API_KEY` | P5 regulatory mentions | free at api.data.gov |
| `COURTLISTENER_API_TOKEN` | P2 (optional but recommended — raises rate limits) | free account at courtlistener.com |
| `CONTACT_EMAIL` | polite User-Agent (SEC requires it) | your email |
| `OPENFDA_API_KEY` | optional, raises openFDA limits | free at open.fda.gov |

## The pipelines

| # | What it measures | Thesis trigger | Sources |
|---|---|---|---|
| P1 | Consultant headcount over ~20 years + live roster | growth from volume, not rate alone | Wayback Machine CDX, exponent.com directory |
| P2 | Courtroom footprint + Daubert exclusion rate | litigation moat intact | CourtListener v4 API |
| P3 | Severity-weighted product-failure index | reactive pipeline filling | NHTSA, CPSC, openFDA |
| P4 | Publications + corporate co-authorship network | scientific moat maintained | OpenAlex |
| P5 | Federal contracts + rulemaking mentions | credibility anchor / risk sensor | USAspending, Regulations.gov |
| P6 | Revealed clients' R&D budgets | proactive demand recovering | derived list + SEC EDGAR XBRL |

## Notes on P2 (CourtListener)

The free tier allows a limited number of API requests per day. `src/p2_litigation`
keeps a daily ledger (`data/interim/p2_quota.json`), caches every response, and
stops cleanly when throttled — **just re-run the same command the next day** and it
resumes from cache. Outputs are written with `status: partial` until complete.

## The no-fabrication contract

Every file in `data/site/` carries a provenance envelope (source URLs, fetch
timestamps, record counts, status `ok|partial|unavailable`, caveats). The
dashboard renders a grey "data unavailable" card when a dataset is missing —
there is no code path that invents a number. `scripts/lint_outputs.py` enforces
the envelope; `scripts/build_site_data.py` refuses to build if any chart lacks
its plain-English methodology explainer.

## Layout

- `src/p1..p6` — pipelines (acquire → cache → build site JSON)
- `src/common` — HTTP cache/rate-limit layer, provenance envelope, SEC client
- `config/` — rate limits, entity name variants, P3 category/severity rules
- `content/explainers/` — beginner-friendly per-chart methodology text
- `data/site/` — canonical pipeline outputs (committed)
- `site/` — the static dashboard (vendored ECharts, no CDN, works offline)
