# indian-market-pipeline

Production-grade Indian capital markets data pipeline. CMOTS-alternative:
ingests NSE, BSE, Screener, Moneycontrol, and AMFI; normalizes into a
Supabase PostgreSQL warehouse; exposes a FastAPI REST surface; runs on
APScheduler with per-source circuit breakers and Prometheus metrics.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        APScheduler (IST)                          │
│   5min: NSE prices · gainers · indices       (market hours only)  │
│  10min: Moneycontrol news                                         │
│  15min: BSE filings                                               │
│  daily 01:00 BSE master | 02:00 Screener | 07:00 AMFI NAV         │
└──────────────────┬───────────────────────────────────────────────┘
                   │ run()
                   ▼
        ┌────────────────────────┐     ┌──────────────────────┐
        │   BaseScraper          │     │  CircuitBreaker      │
        │  (retry + UA rotate)   │◀───▶│  closed/open/half    │
        └─────────┬──────────────┘     └──────────────────────┘
        ┌────┬────┼────┬─────────┬──────────┐
   ┌────▼─┐ │ ┌──▼──┐ │ ┌──────▼─┐ ┌──────▼─┐  ┌────▼───┐
   │ NSE  │ │ │ BSE │ │ │Screener│ │   MC   │  │  AMFI  │
   │ http │ │ │http │ │ │playwgt │ │playwgt │  │  http  │
   └──┬───┘ │ └──┬──┘ │ └──┬─────┘ └──┬─────┘  └──┬─────┘
      └─────┴────┴────┴────┴──────────┴───────────┘
                       │
                       ▼
              ┌──────────────────┐
              │   normalization  │  ←─ currency · pct · symbol · date
              └─────────┬────────┘
                       ▼
   ┌──────────────────────────────────────────────────────┐
   │   DBService (asyncpg pool, ON CONFLICT UPSERT)       │
   │   Supabase Postgres ← RLS · BRIN · partial indexes   │
   └──────────────────────┬───────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐         ┌──────────────┐
              │  FastAPI + Uvicorn    │  ────▶  │ Redis cache  │
              │  /health · /metrics   │         │ (4 min TTL)  │
              │  /stocks /financials  │         └──────────────┘
              │  /news /mutual-funds  │
              │  /indices /admin/...  │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Prometheus + Grafana  │
              └───────────────────────┘
```

---

## Storage backends

The pipeline can write to a **local SQLite file** (default — zero setup)
or to **Supabase Postgres**. Switch via one env var:

```env
STORAGE_BACKEND=sqlite     # default — data/market.sqlite
STORAGE_BACKEND=supabase   # uses DATABASE_URL + SUPABASE_*
STORAGE_BACKEND=both       # tee writes; reads served from Supabase
```

Both backends speak the same `Storage` protocol — scrapers and API
routers don't know which one is active. SQLite gets you ingesting in
~60 seconds; flip to Supabase when you want hosted, multi-reader access.

---

## Quick start (local, SQLite)

### Prereqs
- Python **3.12+**

### 1. Install + initialize

```bash
python -m venv .venv && source .venv/bin/activate     # bash
# .venv\Scripts\Activate.ps1                          # PowerShell
pip install -r requirements-dev.txt
python -m playwright install chromium

cp .env.example .env
# Default .env values already point at sqlite + data/market.sqlite

python -m scripts.init_local_db                       # creates data/market.sqlite
```

### 2. Ingest your first dataset

```bash
# AMFI (~15k mutual fund NAV rows in one shot, no anti-bot)
python -m scripts.ingest_once amfi

# Inspect what landed
sqlite3 data/market.sqlite "SELECT COUNT(*) FROM mutual_funds;"
sqlite3 data/market.sqlite \
  "SELECT scheme_name, nav, nav_date FROM mutual_funds LIMIT 5;"
```

Other one-shot runs:
```bash
python -m scripts.ingest_once nse --task prices
python -m scripts.ingest_once nse --task gainers_losers
python -m scripts.ingest_once bse --task master
python -m scripts.ingest_once screener
```

### 3. Boot the API + scheduler

```bash
uvicorn api.main:app --reload
# → http://localhost:8000/docs
```

### 4. Trigger a scraper via HTTP

```bash
curl -X POST http://localhost:8000/admin/trigger/amfi \
     -H "X-Admin-Key: $ADMIN_API_KEY"

curl -X POST "http://localhost:8000/admin/trigger/nse?task=prices" \
     -H "X-Admin-Key: $ADMIN_API_KEY"
```

---

## Switching to Supabase

When you're ready for a hosted DB:

### 1. Apply the Postgres schema

```bash
# Paste into Supabase SQL Editor:
cat database/schema.sql | pbcopy
# …or run via Alembic after DATABASE_URL is set:
alembic upgrade head
```

### 2. Flip the backend

```env
STORAGE_BACKEND=supabase
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

> **DATABASE_URL note** — Supabase exposes two ports:
> - `:5432` direct (recommended for long-lived workers)
> - `:6543` Supavisor pooler (recommended for serverless/many-connection deploys)
>
> `db_service.py` uses `statement_cache_size=0` so the pooler also works.

### 3. Run with Docker

```bash
docker compose up --build
# API:        http://localhost:8000
# Docs:       http://localhost:8000/docs
# Metrics:    http://localhost:8000/metrics
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3001
```

---

## API surface

| Method | Path                            | Notes                              |
|-------:|---------------------------------|------------------------------------|
| GET    | `/health`                       | DB + Redis + breaker + scraper state |
| GET    | `/stocks`                       | paginated, filter by sector/exchange |
| GET    | `/stock/{symbol}`               | master + latest price + ratios     |
| GET    | `/stock/{symbol}/prices`        | OHLC history (date range)          |
| GET    | `/financials/{symbol}`          | quarterly + annual, filter by period_type |
| GET    | `/news/{symbol}`                | paginated, sentiment filter        |
| GET    | `/mutual-funds`                 | filter by amc / category           |
| GET    | `/mutual-funds/{code}/nav`      | NAV history                        |
| GET    | `/top-gainers` · `/top-losers`  | latest movers                      |
| GET    | `/indices`                      | current snapshot of all indices    |
| GET    | `/metrics`                      | Prometheus exposition              |
| POST   | `/admin/trigger/{scraper}`      | requires `X-Admin-Key` header      |

Full OpenAPI at `/docs`.

---

## Project layout

```
indian-market-pipeline/
├── api/                # FastAPI app + routers
├── core/               # config · logging · exceptions
├── database/           # schema.sql (PG) + schema_sqlite.sql + Alembic
├── scripts/            # init_local_db.py · ingest_once.py
├── models/             # Pydantic v2 schemas + enums
├── scrapers/           # base + 5 sources
├── services/           # db · cache · scheduler · circuit_breaker · normalization
├── tests/              # 30+ unit + API tests
├── observability/      # prometheus.yml + Grafana dashboard
├── docker/             # Dockerfile + entrypoint.sh
├── docker-compose.yml          (dev)
├── docker-compose.prod.yml     (prod overrides)
├── requirements.txt    pinned versions
└── README.md
```

---

## Operational notes

- **Market-hours guard.** Tick-frequency NSE jobs skip outside
  09:15–15:30 IST, Mon–Fri. Filings + news + AMFI run on their own
  cadence regardless of market state. See `services/scheduler.py`.
- **Circuit breakers** are in-memory per scraper. They trip after
  `CIRCUIT_BREAKER_FAIL_THRESHOLD=3` consecutive failures and half-open
  after `CIRCUIT_BREAKER_RESET_SECONDS=60`. Trips emit
  `scraper_failures_total{reason="circuit_open"}`.
- **Anti-bot.** NSE warms cookies via the homepage; Screener and
  Moneycontrol use Playwright + `playwright-stealth`. On Cloudflare 403
  the scraper sleeps 30s and (if `PROXY_URL` is set) rotates proxies.
- **Idempotency.** All UPSERTs use natural composite keys
  (e.g. `(symbol, timestamp)`, `(scheme_code, nav_date)`,
  `url_hash` for news). Re-running a job is safe.
- **Row-Level Security.** All public market data tables grant SELECT to
  `anon` and `authenticated`. Operational tables (run log, slug map,
  checkpoints) are service-role-only.

---

## Tests

```bash
pytest                          # 30+ unit tests (no live network)
pytest -m integration           # integration tests (requires DB + network)
pytest --cov=scrapers --cov=services --cov=api --cov-report=term-missing
```

---

## Caveats

- Live scrapers (NSE/BSE/Screener/Moneycontrol) target current upstream
  layouts. If a site ships HTML/JSON changes, expect to update only the
  affected scraper — selectors and field paths are isolated by source.
- AMFI's `NAVAll.txt` is the only fully-stable upstream contract; its
  scraper is the most resilient.
- Respect upstream ToS and rate limits. The default
  `HTTP_RATE_LIMIT_PER_SOURCE_MS=500` is conservative; tune as needed.

---

See **`docs/DEPLOYMENT.md`** for Railway / Render / AWS ECS instructions.
