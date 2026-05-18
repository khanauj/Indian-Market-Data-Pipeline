-- ════════════════════════════════════════════════════════════════════
-- indian-market-pipeline — full DDL
--
-- Targets Supabase PostgreSQL 15+. Idempotent: safe to re-run.
-- IST-aware: all timestamps are TIMESTAMPTZ.
-- ════════════════════════════════════════════════════════════════════

BEGIN;

-- ─── Extensions ─────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS pgcrypto;        -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS moddatetime;     -- updated_at trigger helper
CREATE EXTENSION IF NOT EXISTS pg_trgm;         -- fuzzy company name search

-- ─── ENUM types ─────────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE exchange_enum AS ENUM ('NSE', 'BSE', 'BOTH');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE period_type_enum AS ENUM ('Q', 'A', 'TTM');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE filing_type_enum AS ENUM (
        'BOARD_MEETING', 'CORPORATE_ACTION', 'DIVIDEND', 'BONUS',
        'SPLIT', 'RIGHTS', 'BUYBACK', 'SHAREHOLDING', 'RESULTS',
        'ANNUAL_REPORT', 'ANNOUNCEMENT', 'OTHER'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE mover_type_enum AS ENUM ('gainer', 'loser');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE scraper_source_enum AS ENUM ('nse', 'bse', 'screener', 'moneycontrol', 'amfi');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE scraper_status_enum AS ENUM ('success', 'partial', 'failed', 'skipped');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ════════════════════════════════════════════════════════════════════
-- Core tables
-- ════════════════════════════════════════════════════════════════════

-- ─── stocks_master ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stocks_master (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(32)  NOT NULL,
    isin            CHAR(12)     UNIQUE,
    company_name    TEXT         NOT NULL,
    exchange        exchange_enum NOT NULL,
    sector          TEXT,
    industry        TEXT,
    market_cap_cr   DOUBLE PRECISION,
    listing_date    DATE,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    raw_payload     JSONB,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT stocks_master_symbol_exchange_uq UNIQUE (symbol, exchange)
);
CREATE INDEX IF NOT EXISTS idx_stocks_master_symbol      ON stocks_master (symbol);
CREATE INDEX IF NOT EXISTS idx_stocks_master_sector      ON stocks_master (sector) WHERE sector IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_stocks_master_active      ON stocks_master (exchange) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_stocks_master_name_trgm   ON stocks_master USING gin (company_name gin_trgm_ops);

DROP TRIGGER IF EXISTS trg_stocks_master_modtime ON stocks_master;
CREATE TRIGGER trg_stocks_master_modtime
    BEFORE UPDATE ON stocks_master
    FOR EACH ROW EXECUTE PROCEDURE moddatetime (updated_at);


-- ─── stock_prices ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stock_prices (
    id                BIGSERIAL PRIMARY KEY,
    symbol            VARCHAR(32)  NOT NULL,
    open              DOUBLE PRECISION,
    high              DOUBLE PRECISION,
    low               DOUBLE PRECISION,
    close             DOUBLE PRECISION,
    ltp               DOUBLE PRECISION,
    volume            BIGINT,
    delivery_qty      BIGINT,
    delivery_pct      DOUBLE PRECISION,
    total_buy_qty     BIGINT,
    total_sell_qty    BIGINT,
    timestamp         TIMESTAMPTZ  NOT NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT stock_prices_symbol_ts_uq UNIQUE (symbol, timestamp)
);
CREATE INDEX IF NOT EXISTS idx_stock_prices_symbol_ts ON stock_prices (symbol, timestamp DESC);
-- BRIN for time-series scans on timestamp (cheap, append-mostly workload)
CREATE INDEX IF NOT EXISTS idx_stock_prices_ts_brin  ON stock_prices USING brin (timestamp);


-- ─── financials ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS financials (
    id                   BIGSERIAL PRIMARY KEY,
    symbol               VARCHAR(32) NOT NULL,
    period_type          period_type_enum NOT NULL,
    period_end_date      DATE NOT NULL,
    revenue_cr           DOUBLE PRECISION,
    ebitda_cr            DOUBLE PRECISION,
    ebitda_margin_pct    DOUBLE PRECISION,
    net_profit_cr        DOUBLE PRECISION,
    eps_ttm              DOUBLE PRECISION,
    pe_ratio             DOUBLE PRECISION,
    pb_ratio             DOUBLE PRECISION,
    roe_pct              DOUBLE PRECISION,
    roce_pct             DOUBLE PRECISION,
    debt_equity_ratio    DOUBLE PRECISION,
    operating_cf_cr      DOUBLE PRECISION,
    free_cf_cr           DOUBLE PRECISION,
    book_value           DOUBLE PRECISION,
    raw_payload          JSONB,
    scraped_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT financials_symbol_period_uq UNIQUE (symbol, period_type, period_end_date)
);
CREATE INDEX IF NOT EXISTS idx_financials_symbol     ON financials (symbol);
CREATE INDEX IF NOT EXISTS idx_financials_period_end ON financials (period_end_date DESC);


-- ─── mutual_funds ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mutual_funds (
    id              BIGSERIAL PRIMARY KEY,
    scheme_code     VARCHAR(32)  NOT NULL,
    isin_payout     VARCHAR(20),
    isin_growth     VARCHAR(20),
    scheme_name     TEXT         NOT NULL,
    amc_name        TEXT,
    category        TEXT,
    sub_category    TEXT,
    nav             DOUBLE PRECISION NOT NULL,
    nav_date        DATE         NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT mutual_funds_scheme_nav_uq UNIQUE (scheme_code, nav_date)
);
CREATE INDEX IF NOT EXISTS idx_mf_scheme_code ON mutual_funds (scheme_code);
CREATE INDEX IF NOT EXISTS idx_mf_nav_date    ON mutual_funds (nav_date DESC);
CREATE INDEX IF NOT EXISTS idx_mf_amc         ON mutual_funds (amc_name) WHERE amc_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_mf_category    ON mutual_funds (category) WHERE category IS NOT NULL;


-- ─── company_filings ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS company_filings (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(32)  NOT NULL,
    filing_type     filing_type_enum NOT NULL,
    title           TEXT         NOT NULL,
    document_url    TEXT,
    filing_date     TIMESTAMPTZ  NOT NULL,
    bse_scrip_code  VARCHAR(16),
    exchange        exchange_enum NOT NULL,
    raw_payload     JSONB,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT filings_symbol_title_date_uq UNIQUE (symbol, title, filing_date)
);
CREATE INDEX IF NOT EXISTS idx_filings_symbol_date ON company_filings (symbol, filing_date DESC);
CREATE INDEX IF NOT EXISTS idx_filings_type        ON company_filings (filing_type);
CREATE INDEX IF NOT EXISTS idx_filings_date_brin   ON company_filings USING brin (filing_date);


-- ─── company_news ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS company_news (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(32) NOT NULL,
    headline        TEXT        NOT NULL,
    url_hash        CHAR(64)    NOT NULL UNIQUE,   -- SHA256(full_url)
    full_url        TEXT        NOT NULL,
    source          TEXT        NOT NULL,
    summary         TEXT,
    sentiment       DOUBLE PRECISION,              -- nullable, NLP fills later
    published_at    TIMESTAMPTZ NOT NULL,
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_news_symbol_pub  ON company_news (symbol, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_pub_brin    ON company_news USING brin (published_at);
CREATE INDEX IF NOT EXISTS idx_news_sentiment   ON company_news (sentiment) WHERE sentiment IS NOT NULL;


-- ─── top_gainers_losers ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS top_gainers_losers (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(32) NOT NULL,
    type            mover_type_enum NOT NULL,
    ltp             DOUBLE PRECISION NOT NULL,
    change_pct      DOUBLE PRECISION NOT NULL,
    volume          BIGINT,
    timestamp       TIMESTAMPTZ NOT NULL,
    CONSTRAINT movers_symbol_type_ts_uq UNIQUE (symbol, type, timestamp)
);
CREATE INDEX IF NOT EXISTS idx_movers_ts_type ON top_gainers_losers (timestamp DESC, type);


-- ─── market_indices ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS market_indices (
    id              BIGSERIAL PRIMARY KEY,
    index_name      VARCHAR(64) NOT NULL,
    open            DOUBLE PRECISION,
    high            DOUBLE PRECISION,
    low             DOUBLE PRECISION,
    close           DOUBLE PRECISION,
    change_pct      DOUBLE PRECISION,
    advances        INTEGER,
    declines        INTEGER,
    timestamp       TIMESTAMPTZ NOT NULL,
    CONSTRAINT indices_name_ts_uq UNIQUE (index_name, timestamp)
);
CREATE INDEX IF NOT EXISTS idx_indices_name_ts ON market_indices (index_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_indices_ts_brin ON market_indices USING brin (timestamp);


-- ════════════════════════════════════════════════════════════════════
-- Operational / support tables
-- ════════════════════════════════════════════════════════════════════

-- ─── scraper_run_log ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scraper_run_log (
    id                  BIGSERIAL PRIMARY KEY,
    source              scraper_source_enum NOT NULL,
    status              scraper_status_enum NOT NULL,
    records_inserted    INTEGER NOT NULL DEFAULT 0,
    records_skipped     INTEGER NOT NULL DEFAULT 0,
    error_msg           TEXT,
    started_at          TIMESTAMPTZ NOT NULL,
    ended_at            TIMESTAMPTZ,
    duration_ms         INTEGER GENERATED ALWAYS AS (
        CASE WHEN ended_at IS NULL THEN NULL
             ELSE EXTRACT(EPOCH FROM (ended_at - started_at)) * 1000 END
    ) STORED
);
CREATE INDEX IF NOT EXISTS idx_run_log_source_started ON scraper_run_log (source, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_run_log_failures ON scraper_run_log (source, started_at DESC) WHERE status = 'failed';


-- ─── symbol_slug_map ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS symbol_slug_map (
    id              BIGSERIAL PRIMARY KEY,
    nse_symbol      VARCHAR(32) NOT NULL UNIQUE,
    bse_code        VARCHAR(16),
    screener_slug   VARCHAR(64),
    mc_slug         VARCHAR(128),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_slug_bse ON symbol_slug_map (bse_code) WHERE bse_code IS NOT NULL;

DROP TRIGGER IF EXISTS trg_slug_modtime ON symbol_slug_map;
CREATE TRIGGER trg_slug_modtime
    BEFORE UPDATE ON symbol_slug_map
    FOR EACH ROW EXECUTE PROCEDURE moddatetime (updated_at);


-- ─── scraper_checkpoints ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scraper_checkpoints (
    source              scraper_source_enum PRIMARY KEY,
    last_run_at         TIMESTAMPTZ,
    last_success_at     TIMESTAMPTZ,
    cursor_value        TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS trg_checkpoint_modtime ON scraper_checkpoints;
CREATE TRIGGER trg_checkpoint_modtime
    BEFORE UPDATE ON scraper_checkpoints
    FOR EACH ROW EXECUTE PROCEDURE moddatetime (updated_at);


-- ════════════════════════════════════════════════════════════════════
-- Row-Level Security (Supabase)
-- ────────────────────────────────────────────────────────────────────
-- Strategy: lock down all market data tables to the service role.
-- The anon role can SELECT public data via PostgREST; nothing else.
-- ════════════════════════════════════════════════════════════════════

ALTER TABLE stocks_master         ENABLE ROW LEVEL SECURITY;
ALTER TABLE stock_prices          ENABLE ROW LEVEL SECURITY;
ALTER TABLE financials            ENABLE ROW LEVEL SECURITY;
ALTER TABLE mutual_funds          ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_filings       ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_news          ENABLE ROW LEVEL SECURITY;
ALTER TABLE top_gainers_losers    ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_indices        ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraper_run_log       ENABLE ROW LEVEL SECURITY;
ALTER TABLE symbol_slug_map       ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraper_checkpoints   ENABLE ROW LEVEL SECURITY;

-- Read-only public access for market data
DO $$
DECLARE
    t TEXT;
    public_tables TEXT[] := ARRAY[
        'stocks_master', 'stock_prices', 'financials', 'mutual_funds',
        'company_filings', 'company_news', 'top_gainers_losers', 'market_indices'
    ];
BEGIN
    FOREACH t IN ARRAY public_tables LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON %I;', t || '_anon_read', t);
        EXECUTE format(
            'CREATE POLICY %I ON %I FOR SELECT TO anon, authenticated USING (true);',
            t || '_anon_read', t
        );
    END LOOP;
END $$;

-- Operational tables: service role only (no anon policy => denied)
-- supabase service_role bypasses RLS, so no explicit policy is required.

COMMIT;

-- ════════════════════════════════════════════════════════════════════
-- Useful views
-- ════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW v_latest_prices AS
SELECT DISTINCT ON (symbol)
    symbol, open, high, low, close, ltp, volume,
    delivery_qty, delivery_pct, timestamp
FROM stock_prices
ORDER BY symbol, timestamp DESC;

CREATE OR REPLACE VIEW v_latest_index_snapshot AS
SELECT DISTINCT ON (index_name)
    index_name, open, high, low, close, change_pct,
    advances, declines, timestamp
FROM market_indices
ORDER BY index_name, timestamp DESC;

CREATE OR REPLACE VIEW v_scraper_health AS
SELECT
    source,
    MAX(started_at) FILTER (WHERE status = 'success')                AS last_success_at,
    MAX(started_at)                                                  AS last_run_at,
    COUNT(*) FILTER (WHERE status = 'failed'
                       AND started_at > now() - INTERVAL '1 hour')    AS failures_last_hour,
    AVG(duration_ms) FILTER (WHERE started_at > now() - INTERVAL '1 day') AS avg_duration_ms_1d
FROM scraper_run_log
GROUP BY source;
