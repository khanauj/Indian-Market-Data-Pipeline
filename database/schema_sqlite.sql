-- ════════════════════════════════════════════════════════════════════
-- indian-market-pipeline — SQLite schema
--
-- Drop-in local equivalent of schema.sql. Differences:
--   • No ENUMs            → TEXT + CHECK constraints
--   • No JSONB            → TEXT (store as JSON string)
--   • No BRIN             → regular B-tree only
--   • No RLS              → file-level access
--   • No moddatetime      → AFTER UPDATE triggers per table
--   • TIMESTAMPTZ → TEXT  (ISO 8601 strings, UTC)
--   • Idempotent: re-runnable.
-- ════════════════════════════════════════════════════════════════════

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- ─── stocks_master ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stocks_master (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    isin            TEXT UNIQUE,
    company_name    TEXT NOT NULL,
    exchange        TEXT NOT NULL CHECK (exchange IN ('NSE','BSE','BOTH')),
    sector          TEXT,
    industry        TEXT,
    market_cap_cr   REAL,
    listing_date    TEXT,           -- ISO date
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    raw_payload     TEXT,           -- JSON
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (symbol, exchange)
);
CREATE INDEX IF NOT EXISTS idx_stocks_master_symbol ON stocks_master (symbol);
CREATE INDEX IF NOT EXISTS idx_stocks_master_sector ON stocks_master (sector);
CREATE INDEX IF NOT EXISTS idx_stocks_master_active ON stocks_master (exchange) WHERE is_active = 1;

CREATE TRIGGER IF NOT EXISTS trg_stocks_master_modtime
    AFTER UPDATE ON stocks_master
    FOR EACH ROW WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE stocks_master SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = NEW.id;
END;


-- ─── stock_prices ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stock_prices (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol            TEXT NOT NULL,
    open              REAL,
    high              REAL,
    low               REAL,
    close             REAL,
    ltp               REAL,
    volume            INTEGER,
    delivery_qty      INTEGER,
    delivery_pct      REAL,
    total_buy_qty     INTEGER,
    total_sell_qty    INTEGER,
    timestamp         TEXT NOT NULL,
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (symbol, timestamp)
);
CREATE INDEX IF NOT EXISTS idx_stock_prices_symbol_ts ON stock_prices (symbol, timestamp DESC);


-- ─── financials ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS financials (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol               TEXT NOT NULL,
    period_type          TEXT NOT NULL CHECK (period_type IN ('Q','A','TTM')),
    period_end_date      TEXT NOT NULL,
    revenue_cr           REAL,
    ebitda_cr            REAL,
    ebitda_margin_pct    REAL,
    net_profit_cr        REAL,
    eps_ttm              REAL,
    pe_ratio             REAL,
    pb_ratio             REAL,
    roe_pct              REAL,
    roce_pct             REAL,
    debt_equity_ratio    REAL,
    operating_cf_cr      REAL,
    free_cf_cr           REAL,
    book_value           REAL,
    raw_payload          TEXT,
    scraped_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (symbol, period_type, period_end_date)
);
CREATE INDEX IF NOT EXISTS idx_financials_symbol     ON financials (symbol);
CREATE INDEX IF NOT EXISTS idx_financials_period_end ON financials (period_end_date DESC);


-- ─── mutual_funds ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mutual_funds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_code     TEXT NOT NULL,
    isin_payout     TEXT,
    isin_growth     TEXT,
    scheme_name     TEXT NOT NULL,
    amc_name        TEXT,
    category        TEXT,
    sub_category    TEXT,
    nav             REAL NOT NULL,
    nav_date        TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (scheme_code, nav_date)
);
CREATE INDEX IF NOT EXISTS idx_mf_scheme_code ON mutual_funds (scheme_code);
CREATE INDEX IF NOT EXISTS idx_mf_nav_date    ON mutual_funds (nav_date DESC);
CREATE INDEX IF NOT EXISTS idx_mf_amc         ON mutual_funds (amc_name);
CREATE INDEX IF NOT EXISTS idx_mf_category    ON mutual_funds (category);


-- ─── company_filings ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS company_filings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    filing_type     TEXT NOT NULL CHECK (filing_type IN (
        'BOARD_MEETING','CORPORATE_ACTION','DIVIDEND','BONUS','SPLIT','RIGHTS',
        'BUYBACK','SHAREHOLDING','RESULTS','ANNUAL_REPORT','ANNOUNCEMENT','OTHER'
    )),
    title           TEXT NOT NULL,
    document_url    TEXT,
    filing_date     TEXT NOT NULL,
    bse_scrip_code  TEXT,
    exchange        TEXT NOT NULL CHECK (exchange IN ('NSE','BSE','BOTH')),
    raw_payload     TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (symbol, title, filing_date)
);
CREATE INDEX IF NOT EXISTS idx_filings_symbol_date ON company_filings (symbol, filing_date DESC);
CREATE INDEX IF NOT EXISTS idx_filings_type        ON company_filings (filing_type);


-- ─── company_news ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS company_news (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    headline        TEXT NOT NULL,
    url_hash        TEXT NOT NULL UNIQUE,
    full_url        TEXT NOT NULL,
    source          TEXT NOT NULL,
    summary         TEXT,
    sentiment       REAL,
    published_at    TEXT NOT NULL,
    scraped_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_news_symbol_pub ON company_news (symbol, published_at DESC);


-- ─── top_gainers_losers ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS top_gainers_losers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN ('gainer','loser')),
    ltp             REAL NOT NULL,
    change_pct      REAL NOT NULL,
    volume          INTEGER,
    timestamp       TEXT NOT NULL,
    UNIQUE (symbol, type, timestamp)
);
CREATE INDEX IF NOT EXISTS idx_movers_ts_type ON top_gainers_losers (timestamp DESC, type);


-- ─── market_indices ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS market_indices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    index_name      TEXT NOT NULL,
    open            REAL,
    high            REAL,
    low             REAL,
    close           REAL,
    change_pct      REAL,
    advances        INTEGER,
    declines        INTEGER,
    timestamp       TEXT NOT NULL,
    UNIQUE (index_name, timestamp)
);
CREATE INDEX IF NOT EXISTS idx_indices_name_ts ON market_indices (index_name, timestamp DESC);


-- ─── scraper_run_log ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scraper_run_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    source              TEXT NOT NULL CHECK (source IN ('nse','bse','screener','moneycontrol','amfi')),
    status              TEXT NOT NULL CHECK (status IN ('success','partial','failed','skipped')),
    records_inserted    INTEGER NOT NULL DEFAULT 0,
    records_skipped     INTEGER NOT NULL DEFAULT 0,
    error_msg           TEXT,
    started_at          TEXT NOT NULL,
    ended_at            TEXT,
    duration_ms         REAL GENERATED ALWAYS AS (
        CASE WHEN ended_at IS NULL THEN NULL
             ELSE (julianday(ended_at) - julianday(started_at)) * 86400000 END
    ) STORED
);
CREATE INDEX IF NOT EXISTS idx_run_log_source_started ON scraper_run_log (source, started_at DESC);


-- ─── symbol_slug_map ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS symbol_slug_map (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nse_symbol      TEXT NOT NULL UNIQUE,
    bse_code        TEXT,
    screener_slug   TEXT,
    mc_slug         TEXT,
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_slug_bse ON symbol_slug_map (bse_code);

CREATE TRIGGER IF NOT EXISTS trg_slug_modtime
    AFTER UPDATE ON symbol_slug_map
    FOR EACH ROW WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE symbol_slug_map SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id = NEW.id;
END;


-- ─── scraper_checkpoints ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scraper_checkpoints (
    source              TEXT PRIMARY KEY CHECK (source IN ('nse','bse','screener','moneycontrol','amfi')),
    last_run_at         TEXT,
    last_success_at     TEXT,
    cursor_value        TEXT,
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);


-- ════════════════════════════════════════════════════════════════════
-- Views (latest snapshot helpers)
-- ════════════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_latest_prices;
CREATE VIEW v_latest_prices AS
SELECT p.* FROM stock_prices p
JOIN (
    SELECT symbol, MAX(timestamp) AS max_ts FROM stock_prices GROUP BY symbol
) latest ON latest.symbol = p.symbol AND latest.max_ts = p.timestamp;

DROP VIEW IF EXISTS v_latest_index_snapshot;
CREATE VIEW v_latest_index_snapshot AS
SELECT i.* FROM market_indices i
JOIN (
    SELECT index_name, MAX(timestamp) AS max_ts FROM market_indices GROUP BY index_name
) latest ON latest.index_name = i.index_name AND latest.max_ts = i.timestamp;
