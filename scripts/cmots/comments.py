"""CMOTS Comments — implementation notes, source limitations, DQ, mappings."""

CMOTS_COMMENTS = [
    ("Data Source Strategy",
     "NSE/BSE serve as primary for prices, OHLC, indices, corporate actions, announcements. "
     "Screener is primary for financial statements and ratios. Trendlyne supplements FII/DII "
     "and brokerage data. AMFI is authoritative for mutual fund NAV. Yahoo Finance is the "
     "historical price fallback when NSE Bhavcopy is unavailable."),

    ("NSE Anti-Bot Mitigation",
     "NSE public API requires browser-like session: hit homepage first to populate "
     "nseappid + bm_sv cookies, then issue API calls. Cookies expire — re-warm on 401/403. "
     "Rotate User-Agent from a pool of recent desktop browsers. NSE will silently rate-limit "
     "abusive IPs — keep rate <= 1 request per 500ms per endpoint."),

    ("BSE Filings Latency",
     "BSE corporate filings have variable upload latency (5 min to 2 hours after submission). "
     "Poll every 15 minutes during 09:00-18:00 IST. Use disseminated_at_ist as the canonical "
     "timestamp, not submitted_at. Deduplicate via SHA256 hash of attachment URL."),

    ("Screener Playwright Requirement",
     "Screener.in serves financial statements as server-rendered HTML behind Cloudflare. "
     "Plain httpx returns 403. Use Playwright Chromium with playwright-stealth plugin. "
     "Throttle to one company per 2 seconds. Cache results aggressively — Screener data "
     "changes only quarterly."),

    ("Moneycontrol News Volume",
     "Moneycontrol publishes 200-300 news items per day across all companies. Poll every "
     "10 minutes is sufficient — sub-second freshness not achievable from free sources. "
     "Use url_hash as idempotency key. Sentiment scoring via FinBERT or VADER finance model."),

    ("AMFI NAVAll Reliability",
     "AMFI NAVAll.txt is the most stable upstream — single flat file, no anti-bot, "
     "deterministic format. Update at 23:00 IST after market close. Some schemes show "
     "N.A. on holidays or post-merger — handle gracefully (skip row, don't fail run)."),

    ("AMC Portfolio Disclosure Delay",
     "SEBI mandates AMCs disclose portfolios within 10 days of month-end. AMCs publish "
     "PDF disclosures on websites between 5th-10th of next month. Trendlyne aggregates "
     "these but has 2-3 day lag. Plan ingest job for 11th of month, 03:00 IST."),

    ("FII/DII Granularity Limitation",
     "Free sources expose top-N FII/DII holders only, not the long tail. Full institutional "
     "holdings (every FII with > 1% stake) requires Bloomberg or direct NSDL FPI feed. "
     "Acceptable workaround: aggregate Cat-I and Cat-II FPI numbers from NSDL daily "
     "deposit data."),

    ("Trendlyne Authentication",
     "Trendlyne free tier has 50 requests/day per IP. Premium API at INR 25k/year unlocks "
     "10k requests/day. For production scale (~5000 companies daily) the premium plan is "
     "non-negotiable. Free tier acceptable for initial dev only."),

    ("Yahoo Finance Symbol Mapping",
     "Yahoo Finance uses suffix .NS for NSE (e.g. RELIANCE.NS) and .BO for BSE "
     "(e.g. RELIANCE.BO). Maintain symbol_alias_map table. Yahoo data sometimes lags "
     "real-time by 15-30 minutes for free tier — use only for historical backfill."),

    ("Block vs Bulk Deal Distinction",
     "Block deals: single trade > INR 10 crore, executed in special 5-min window 09:00-09:05. "
     "Bulk deals: any client trading > 0.5% of equity in a day. Both reported separately by "
     "NSE/BSE EOD. Store in same table with deal_type discriminator column."),

    ("Insider Trading SAST vs PIT",
     "SEBI SAST regulations: promoter/director must disclose acquisition within 2 days. "
     "PIT regulations: insiders disclose all trades exceeding INR 10 lakh. We capture both "
     "feeds. Reconcile by matching (symbol, acquirer_name, transaction_date, quantity) — "
     "deduplicate identical rows."),

    ("Stock Split Adjustment Logic",
     "When applying split adjustment to historical prices, divide all pre-ex-date OHLC and "
     "multiply volume by ratio. Maintain cumulative adjustment_factor in stock_ohlc_adjusted. "
     "Bonus issues: same logic with bonus ratio + 1. Dividends: subtract dividend amount "
     "from price on ex-date (total return convention)."),

    ("Materialized Views for Performance",
     "Rolling computations (52-week H/L, returns, beta, std dev) on 5M+ price rows require "
     "materialized views in Postgres. Refresh via pg_cron after EOD ingest. Use BRIN indexes "
     "on (symbol, trade_date) for time-series tables — 50x smaller than B-tree."),

    ("Partitioning Strategy",
     "stock_prices and stock_ohlc_intraday partitioned monthly by timestamp. mf_nav_history "
     "partitioned yearly. Pre-create partitions 30 days in advance via script. Use "
     "PostgreSQL native range partitioning. Old partitions (>2 years) detached and moved "
     "to S3 for cold storage."),

    ("Idempotency on Re-runs",
     "Every UPSERT uses natural composite keys: stocks_master(isin), stock_prices(symbol, "
     "timestamp), corporate_actions(symbol, action_type, ex_date), mutual_funds(scheme_code, "
     "nav_date), news(url_hash). Re-running any job is safe — no duplicates, latest data wins."),

    ("Symbol Normalization",
     "NSE uses uppercase alphanumeric (RELIANCE, M&M, AYM-SYNTEX). BSE uses both numeric "
     "codes (500325) and scrip names (RELIANCE). Normalize all storage to NSE convention. "
     "Maintain symbol_alias_map for special characters (M&M -> MM in some sources)."),

    ("Currency & Unit Normalization",
     "All monetary values stored as NUMERIC in INR. Convert lakhs to crores at ingest "
     "(1 crore = 100 lakhs). Suffix column names with _cr or _lakh to make units explicit. "
     "Foreign currency revenue (IT services) converted to INR at quarter-end rate."),

    ("Date Format Handling",
     "Sources use mixed formats: DD-Mon-YYYY (AMFI), YYYY-MM-DD (NSE), DD/MM/YYYY (BSE). "
     "Normalize all to ISO 8601 (YYYY-MM-DD) at ingest. Store IST timestamps with explicit "
     "timezone — never naive datetimes. Bhavcopy timestamps are end-of-trading-day 15:30 IST."),

    ("Validation: Shareholding Sum",
     "Sum of (promoter + FII + DII + retail + HNI + bodies + others) must equal "
     "100 +/- 1% (rounding tolerance). If outside band, flag in data_quality_log with "
     "severity=warning. Likely cause: source rounding or undisclosed category."),

    ("Validation: OHLC Sanity",
     "high >= max(open, low, close) AND low <= min(open, high, close). Volume >= 0. "
     "trade_date <= today AND is weekday. Violations dropped at normalize() stage with "
     "warning log. Critical violations (negative volume) page on-call."),

    ("Validation: NAV Bounds",
     "NAV must be > 0 AND < 100,000. Day-over-day change > 20% on equity scheme is "
     "suspicious — flag for manual review. Some debt schemes show large jumps on "
     "credit events (DHFL 2019, Franklin 2020) — those are valid and confirmed manually."),

    ("Cross-Source Reconciliation",
     "NSE vs Yahoo close-price disagreement > 0.5% logged as warning. NSE wins by default. "
     "Screener vs BSE financial result disagreement on PAT > 1% triggers manual review. "
     "Maintain reconciliation_results table for audit trail."),

    ("Missing Data Imputation",
     "OHLC gaps (suspension days, holidays) — DO NOT impute, leave null. Returns calculations "
     "exclude null rows. NAV gaps on weekends/holidays — forward-fill last NAV for "
     "presentation, but mark as is_carried_forward=true in API response."),

    ("Real-Time vs Delayed Quotes",
     "Free NSE API serves 5-15 second delayed quotes. True real-time (sub-second tick) "
     "requires NSE colo or paid feed (Truedata, Zerodha Kite). Free Yahoo Finance is "
     "15-min delayed. Document delay in API response meta.delay_seconds field."),

    ("Currency Derivatives Coverage Gap",
     "USD-INR, EUR-INR, GBP-INR, JPY-INR futures and options not covered by current "
     "scrapers. NSE Currency Derivatives segment requires separate scraper. Add to "
     "roadmap if FX exposure required."),

    ("Commodity (MCX) Out of Scope",
     "MCX (gold, silver, crude, copper, agri) is a separate exchange with its own API "
     "(mcxindia.com). Current architecture is equity-and-MF only. MCX scraper would "
     "extend BaseScraper pattern but is roadmap item, not current build."),

    ("Bond and G-Sec Yields",
     "Corporate bond data: BSE has limited coverage at https://www.bseindia.com/markets/Debt/. "
     "G-Sec: NDS-OM via CCIL has full coverage but requires SFTP credentials. Currently "
     "not in scope — document as roadmap if fixed-income data required."),

    ("Annual Report PDF Extraction",
     "Footnotes, accounting policies, related-party transactions are in AR PDFs only. "
     "Tabula or pdfplumber for text extraction, Tesseract OCR for scanned tables. Quarterly "
     "expense: ~INR 10k cloud OCR for 5000 companies. Recommendation: subset top-500 "
     "companies for AR enrichment."),

    ("ESG and Governance Scores",
     "MSCI/Sustainalytics/Refinitiv ESG scores require paid subscriptions. Build internal "
     "score from: board composition (% independent), audit firm rotation history, "
     "related-party transactions volume, employee turnover, CSR spend vs mandate."),

    ("Analyst Estimates Coverage",
     "Trendlyne has consensus EPS estimates for top-500 stocks. Smaller stocks have "
     "limited or no coverage. Mark missing-coverage flag explicitly in API output. Do "
     "not impute or extrapolate analyst estimates."),

    ("Smart Beta / Factor Scores",
     "Value, Momentum, Quality, Low-Vol factor scores computed in-house from ratios + price. "
     "Reference implementation: standardize Z-scores within sector, then combine with "
     "configurable weights. Refresh quarterly. Not yet productized — roadmap."),

    ("Pre-Merger Symbol History",
     "When companies merge (HDFC-HDFC Bank 2023), historical ticker continuity breaks. "
     "Maintain historical_alias table mapping old symbol -> new symbol with effective_date. "
     "Pre-merger prices accessible via old symbol; charts stitched at application layer."),

    ("F&O Greeks Calculation",
     "NSE does not publish option Greeks — compute server-side via Black-Scholes. Inputs: "
     "spot, strike, time to expiry, risk-free rate, IV. IV reverse-engineered from market "
     "premium via Newton-Raphson. Cache per (instrument_id, timestamp) — 5s TTL during "
     "market hours."),

    ("F&O OI Cross-Validation",
     "NSE F&O OI from public API sometimes lags by 1-2 minutes vs broker terminals. Cross-"
     "validate against TradingView and CME Group ICE feeds for index futures. Discrepancies "
     "> 5% logged as warning."),

    ("Insider Trading Acquirer Categorization",
     "BSE SAST filings classify acquirers as Promoter/KMP/Director/Connected. Some filings "
     "have ambiguous category (e.g. promoter spouse). Apply heuristic: if acquirer name "
     "appears in company_directors table, tag as Director; else Connected."),

    ("Pledged Shares Disclosure",
     "Pledge data disclosed quarterly with shareholding pattern + ad-hoc on creation/release "
     "of pledge (Reg 31 of SAST). Capture both — ad-hoc events overwrite quarterly snapshot "
     "for accuracy. Significant pledges (> 50% of promoter holding) flagged as material event."),

    ("Brokerage Recommendation Deduplication",
     "Same brokerage may issue multiple recos on same day (initial coverage + earnings update). "
     "Dedup key: (symbol, broker_name, recommendation_date, target_price). Update existing row "
     "if target_price unchanged but rating changes."),

    ("Earnings Calendar Source Reliability",
     "Trendlyne and Moneycontrol publish earnings calendars but with 60-70% accuracy. "
     "Override with BSE board meetings table which is authoritative once company announces "
     "result date. Display estimate dates with confidence flag."),

    ("Data Quality Nightly Checks",
     "Run at 23:30 IST daily: (1) every active NSE symbol has OHLC for latest trading day, "
     "(2) no >5 trading-day gap per symbol, (3) shareholding % sums to ~100, (4) FK soft "
     "check mf_holdings.symbol -> stocks_master.nse_symbol, (5) source freshness within SLA. "
     "Failures pages on-call via Slack/Telegram."),

    ("API Rate Limiting Strategy",
     "600 req/min per API key default. Premium tiers: 2400 (paid), 10k (enterprise). "
     "Implement via Redis token-bucket. Return 429 with Retry-After header on breach. "
     "Whitelist internal services bypass rate limit via service-account JWT."),

    ("Cache TTL Tuning",
     "Live quotes: 5 sec TTL. Top gainers/losers: 5 min. OHLC daily: 1 hour. Company "
     "master: 6 hours. MF NAV: 30 min after release. Financial ratios: 24 hours. "
     "Materialized views (52w, returns) refreshed nightly, served forever."),

    ("Supabase RLS Policy",
     "All public market data tables: SELECT to anon and authenticated. Operational tables "
     "(scraper_run_log, scraper_checkpoints, data_quality_log) service-role-only. User-"
     "scoped data (watchlists, portfolios) tagged with user_id and policy filters by "
     "auth.uid()."),

    ("Disaster Recovery",
     "Supabase daily automated backups (retained 7 days on standard plan, 30 on pro). "
     "Weekly logical dump via pg_dump to S3. RTO: 4 hours. RPO: 24 hours. Scrapers idempotent "
     "so replaying last 24 hours of ingest is the recovery procedure for data loss."),

    ("Cost Estimation (Production)",
     "Supabase Pro ~USD 25/mo + storage. Redis (Upstash) ~USD 10/mo. Compute (Railway/ECS) "
     "~USD 50/mo for API + scheduler + real-time ingestor. Trendlyne premium INR 25k/yr. "
     "Cloud OCR for AR PDFs ~USD 100/mo at top-500 scope. Total: ~USD 200-300/mo + "
     "INR 25k Trendlyne. Cheaper than CMOTS license (INR 5-15 lakh/year)."),

    ("Compliance and SEBI Considerations",
     "Distributing market data to end clients requires SEBI Data Distributor license under "
     "SEBI (RA & IA) Regulations. Internal use (own trading or research) is exempt. Consult "
     "compliance team before commercial API offering. Display data-source attribution per "
     "exchange ToS (NSE requires logo, BSE requires text credit)."),

    ("Performance Benchmarks",
     "API p99 latency target: <200ms cached, <800ms uncached. Real-time price lag target: "
     "<6 sec. Daily Bhavcopy ingest target: <5 min after 18:30 IST release. AMFI NAV "
     "ingest: <30 sec for 22k schemes. Concurrent users: 1000 RPS sustained."),

    ("Scalability Path",
     "Current architecture (single-process FastAPI + scheduler) sustains 5000 symbols, "
     "1000 RPS. For 50k symbols or 10k RPS: split into (1) stateless API workers behind "
     "ALB, (2) single scheduler worker, (3) dedicated real-time ingestor, (4) Redis cluster "
     "instead of single Redis. Postgres remains single Supabase instance."),

    ("Frontend Integration",
     "Recommended stack: Next.js + React Query for dashboards, recharts/visx for charts, "
     "Supabase JS client for direct row-level queries (RLS-protected), FastAPI for "
     "computed/aggregated endpoints. Cache invalidation via Supabase Realtime subscriptions "
     "on materialized view refresh."),

    ("Failed Run Alerting",
     "Scraper run with status=FAILED auto-posts to Slack/Telegram via ALERT_WEBHOOK_URL. "
     "Include: source, task, error_message, last_success_at. Open-on-call rotation defined "
     "in PagerDuty. SLA: respond within 1 hour for market-hours failures, 4 hours otherwise."),

    ("Data Retention Policy",
     "Hot (Postgres primary): 90 days intraday, 5 years daily OHLC, 10 years financials, "
     "all NAV history, all corporate actions. Warm (Postgres archive partitions): 90d-2yr "
     "intraday. Cold (S3 Parquet): >2 years intraday, raw ingest logs. Compress with zstd."),

    ("Roadmap: Currency Derivatives, MCX, Bonds",
     "Three sources currently out of scope but architecturally identical: add new BaseScraper "
     "subclass per source, new tables, new APIs. Estimated effort: 2 weeks per source. "
     "Prioritize based on user demand."),

    ("Roadmap: Real-Time WebSocket Feed",
     "Current implementation is poll-based (5s NSE poll). For sub-second latency, subscribe "
     "to NSE WebSocket (via paid broker API like Zerodha Kite Connect or AngelOne SmartAPI). "
     "Architecture: dedicated websocket worker -> Redis pub/sub -> SSE/WebSocket out to clients."),

    ("Roadmap: ML Sentiment & Topic Models",
     "Current news sentiment is rule-based (FinBERT/VADER). Roadmap: fine-tune FinBERT on "
     "Moneycontrol corpus, add topic modeling (LDA) for thematic clustering, entity linking "
     "to map news to specific products/management. Quarterly model refresh."),

    ("Roadmap: Portfolio Analytics",
     "User-uploaded portfolio (CSV or broker integration) gets returns, attribution, factor "
     "exposure, risk decomposition. Requires: portfolios table, transactions table, "
     "computation engine. Estimated effort 3 weeks. Premium tier feature."),

    # ─── Automation & Scheduler Architecture (per latest spec) ──────────────
    ("Daily 18:00 IST EOD Master Trigger",
     "Primary daily batch fires at 18:00 IST Mon-Fri via APScheduler CronTrigger inside "
     "the worker container. Runs NSE prices snapshot, gainers/losers, indices in sequence. "
     "AMFI NAV fires separately at 18:30 IST. Corporate actions consolidate at 22:00 IST. "
     "Job ID: eod_batch_18 — visible in scheduler_run_log table."),

    ("Scheduler Implementation Choice",
     "APScheduler (AsyncIO variant) chosen over Celery Beat / Airflow because: (1) single-"
     "process simplicity matches single Render worker, (2) IST timezone first-class via "
     "ZoneInfo, (3) max_instances=1 + coalesce=True prevents job overlap, (4) no external "
     "broker (Redis/RabbitMQ) needed for the queue. For 10x scale, migrate to Celery + Redis."),

    ("Backup Trigger via GitHub Actions",
     "Belt-and-suspenders: .github/workflows/daily-refresh.yml fires daily at 12:30 UTC "
     "(=18:00 IST), hits /admin/trigger/* endpoints over HTTPS with X-Admin-Key header. "
     "Safety net for when Render worker is sleeping/restarting. Requires repo secrets: "
     "API_BASE_URL, ADMIN_API_KEY. Failures emit ::warning:: annotations."),

    ("Incremental Update Strategy",
     "Every UPSERT uses natural composite keys (ON CONFLICT DO UPDATE). Re-ingesting the "
     "same row updates only the changed fields. Historical price data is append-only "
     "(no DELETE) — partitioning by month keeps queries fast. mf_nav_history partitions "
     "by year. Corporate actions are UPSERT-by-(symbol, action_type, ex_date) so amendments "
     "to announced actions are captured but no duplicates."),

    ("Retry Logic Specification",
     "Tenacity wrapper in BaseScraper._get(): max 4 retries (configurable via HTTP_MAX_RETRIES), "
     "exponential backoff with jitter (1s -> 2s -> 4s -> 8s, cap 30s), retry only on "
     "TimeoutException / HTTPStatusError / RateLimitError. After exhaustion: scraper_failures_total "
     "metric increments with reason=retry_exhausted, run logged FAILED in scraper_run_log."),

    ("Audit Columns (source_name / last_refresh_time / data_version)",
     "Alembic migration 0002_audit_columns adds three audit columns to all ingest tables. "
     "source_name identifies origin scraper (nse/bse/amfi/screener/moneycontrol). last_refresh_time "
     "auto-defaults to NOW() on insert. data_version starts at 1, app-level UPDATE triggers "
     "increment it. Existing rows backfilled with source_name='legacy', data_version=1."),

    ("Refresh Cadence Per Dataset",
     "EOD market data: 18:00 IST daily. AMFI NAV: 18:30 IST daily. Corporate actions: "
     "22:00 IST daily. Shareholding pattern: 25th of Jan/Apr/Jul/Oct at 03:00 IST (quarterly). "
     "Financial statements (Screener): Sunday 02:00 IST weekly (Screener side updates lazily). "
     "Corporate announcements: hourly 09:00-18:00 IST. News: every 30 minutes 24/7. "
     "BSE master: 01:00 IST daily. Real-time prices: every 5 min during market hours only."),

    ("Logging Pipeline (Structured)",
     "structlog JSON to stdout (captured by Render/CloudWatch). Each scraper run emits: "
     "(1) run_ok / run_failed event with source, task, inserted, skipped, duration_s; "
     "(2) row in scraper_run_log table (auditable from SQL); (3) Prometheus counters. "
     "DQ violations land in data_quality_log with severity (info/warning/error/critical). "
     "Schema mismatches (Pydantic ValidationError) drop the row + log to data_quality_log."),

    ("Worker Service Topology on Render",
     "render.yaml defines two services: market-api (web, SCHEDULER_ENABLED=false, serves "
     "/docs and /health) + market-worker (background, SCHEDULER_ENABLED=true, runs ALL "
     "scheduled jobs). Critical: scheduler MUST run in exactly one place; running it in "
     "both web replicas would double every ingest. APScheduler is in-memory (not Redis-"
     "backed) so single-instance constraint is enforced architecturally."),

    ("Historical Data Preservation",
     "Price history, NAV history, corporate actions, shareholding snapshots are NEVER "
     "overwritten. Each ingest of the same (symbol, date) updates current-value fields "
     "but preserves the row. Quarterly shareholding stored as new row per period - "
     "historical comparison is a simple WHERE period_end_date <= X query. Materialized "
     "views (mv_52week, mv_mf_returns) recomputed nightly from full history."),

    ("Failure Alerting",
     "Any scraper run with status=FAILED auto-posts to ALERT_WEBHOOK_URL (Slack/Discord/"
     "Telegram). Payload: source, task, error_class, error_message, last_success_at. "
     "Aggregation: if same source fails 3 consecutive times, circuit opens (no upstream "
     "calls for 60s), Prometheus alert triggers PagerDuty for market-hours, Slack for "
     "off-hours. SLA: 1 hour acknowledgement during 09:15-15:30 IST, 4 hours otherwise."),

    ("Excel Workbook Refresh",
     "The CMOTS_Data_Catalog.xlsx documentation workbook is regenerated by "
     "scripts/build_cmots_excel.py. Run it manually after API spec changes, or wire into "
     "CI to regenerate on every push to main. The workbook contains 95 equity APIs + 40 "
     "MF APIs + this comments sheet with current refresh frequencies and update times. "
     "Source of truth for API contracts."),

    ("Schema Migration Strategy",
     "Alembic for all schema changes. Migration 0001_initial sets up all 38 tables and "
     "indexes. 0002_audit_columns adds source_name / last_refresh_time / data_version "
     "additively (no data loss). Future migrations follow same pattern: additive first, "
     "drop-column in a later release after consumers migrate. Run via "
     "'docker compose run --rm market-api migrate' or scripts/migrate.sh."),

    ("Data Versioning Semantics",
     "data_version starts at 1 on INSERT. App-level handlers increment on every UPDATE "
     "via UPSERT-returning-old-version pattern. Use case: client polling can pass "
     "If-None-Match: <data_version> header and receive 304 Not Modified when unchanged. "
     "Also enables optimistic concurrency control - reject UPDATE if data_version "
     "in WHERE doesn't match current row version."),
]
