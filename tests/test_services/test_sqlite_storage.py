"""Round-trip tests for the SQLite backend.

These run against an on-disk file (tmp_path) rather than :memory: so
WAL mode and the schema application path both get exercised.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from models.enums import Exchange, ScraperSource, ScraperStatus
from models.schemas import (
    CompanyNewsIn,
    MutualFundIn,
    StockMasterIn,
    StockPriceIn,
)
from services.sqlite_storage import SQLiteStorage, _pg_to_sqlite_params


# ─── Pure-function tests (no DB) ────────────────────────────────────
class TestParamTranslation:
    def test_translates_dollar_params(self):
        assert _pg_to_sqlite_params("SELECT * FROM t WHERE a=$1 AND b=$2") \
            == "SELECT * FROM t WHERE a=? AND b=?"

    def test_handles_no_params(self):
        assert _pg_to_sqlite_params("SELECT 1") == "SELECT 1"


# ─── Round-trip tests against a real SQLite file ────────────────────
@pytest.fixture
async def storage(tmp_path):
    path = str(tmp_path / "test.sqlite")
    s = SQLiteStorage(path=path)
    await s.connect()
    yield s
    await s.close()


@pytest.mark.asyncio
class TestSQLiteRoundTrip:
    async def test_schema_applied(self, storage):
        # All 11 tables should exist
        rows = await storage.fetch(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        names = {r["name"] for r in rows}
        expected = {
            "stocks_master", "stock_prices", "financials", "mutual_funds",
            "company_filings", "company_news", "top_gainers_losers",
            "market_indices", "scraper_run_log", "symbol_slug_map",
            "scraper_checkpoints",
        }
        assert expected.issubset(names)

    async def test_upsert_mutual_funds_then_read(self, storage):
        rows = [
            MutualFundIn(
                scheme_code="100033", isin_payout=None, isin_growth="INF209K01165",
                scheme_name="Aditya Birla Sun Life Frontline Equity - Growth",
                amc_name="Aditya Birla Sun Life", category="Equity - Large Cap",
                sub_category="Growth", nav=567.89, nav_date=date(2026, 5, 15),
            ),
            MutualFundIn(
                scheme_code="200001", isin_growth="INF179K01XYZ",
                scheme_name="HDFC Liquid Fund - Direct - Growth",
                amc_name="HDFC", category="Debt - Liquid",
                sub_category="Direct - Growth", nav=3456.78, nav_date=date(2026, 5, 15),
            ),
        ]
        inserted, skipped = await storage.upsert_batch(
            "mutual_funds", rows, conflict_cols=["scheme_code", "nav_date"]
        )
        assert inserted == 2
        assert skipped == 0

        # Idempotency: re-upsert is a no-op (or update) — same final count
        await storage.upsert_batch(
            "mutual_funds", rows, conflict_cols=["scheme_code", "nav_date"]
        )
        count = await storage.fetchval("SELECT COUNT(*) FROM mutual_funds")
        assert count == 2

    async def test_jsonb_roundtrip_decodes_dict(self, storage):
        row = StockMasterIn(
            symbol="RELIANCE", isin="INE002A01018",
            company_name="Reliance Industries Ltd",
            exchange=Exchange.NSE,
            sector="Energy", industry="Oil & Gas",
            raw_payload={"upstream_id": 12345, "tags": ["sensex", "nifty50"]},
        )
        await storage.upsert_batch(
            "stocks_master", [row],
            conflict_cols=["symbol", "exchange"],
            jsonb_cols=["raw_payload"],
        )
        got = await storage.fetchrow(
            "SELECT symbol, raw_payload FROM stocks_master WHERE symbol = $1", "RELIANCE"
        )
        assert got is not None
        # raw_payload should be decoded back to a dict by the storage layer
        assert isinstance(got["raw_payload"], dict)
        assert got["raw_payload"]["upstream_id"] == 12345
        assert got["raw_payload"]["tags"] == ["sensex", "nifty50"]

    async def test_run_log_and_checkpoint(self, storage):
        now = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
        await storage.log_scraper_run(
            source=ScraperSource.AMFI,
            status=ScraperStatus.SUCCESS,
            started_at=now,
            ended_at=now,
            records_inserted=42,
        )
        await storage.update_checkpoint(
            source=ScraperSource.AMFI,
            last_run_at=now,
            last_success_at=now,
        )
        log_row = await storage.fetchrow(
            "SELECT records_inserted FROM scraper_run_log WHERE source = $1",
            ScraperSource.AMFI.value,
        )
        assert log_row is not None
        assert log_row["records_inserted"] == 42

        ckpt = await storage.fetchrow(
            "SELECT last_run_at FROM scraper_checkpoints WHERE source = $1",
            ScraperSource.AMFI.value,
        )
        assert ckpt is not None
        assert ckpt["last_run_at"].startswith("2026-05-15T12:00")

    async def test_news_dedupe_on_url_hash(self, storage):
        now = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
        item = CompanyNewsIn(
            symbol="TCS",
            headline="TCS Q4 beats estimates",
            url_hash="a" * 64,
            full_url="https://example.com/article-1",
            source="moneycontrol",
            published_at=now, scraped_at=now,
        )
        await storage.upsert_batch("company_news", [item], conflict_cols=["url_hash"], update_cols=[])
        # Re-insert: same url_hash → no new row
        await storage.upsert_batch("company_news", [item], conflict_cols=["url_hash"], update_cols=[])
        count = await storage.fetchval("SELECT COUNT(*) FROM company_news")
        assert count == 1
