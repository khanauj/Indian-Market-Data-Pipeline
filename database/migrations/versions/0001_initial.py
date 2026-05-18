"""Initial schema — applies database/schema.sql verbatim.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-15
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None

_SCHEMA_SQL = Path(__file__).resolve().parents[2] / "schema.sql"


def upgrade() -> None:
    sql = _SCHEMA_SQL.read_text(encoding="utf-8")
    # Strip the surrounding BEGIN/COMMIT — Alembic wraps the migration in its own txn.
    sql = sql.replace("BEGIN;", "").replace("COMMIT;", "")
    op.execute(sql)


def downgrade() -> None:
    op.execute(
        """
        DROP VIEW IF EXISTS v_scraper_health, v_latest_index_snapshot, v_latest_prices CASCADE;
        DROP TABLE IF EXISTS
            scraper_checkpoints, symbol_slug_map, scraper_run_log,
            market_indices, top_gainers_losers, company_news, company_filings,
            mutual_funds, financials, stock_prices, stocks_master
            CASCADE;
        DROP TYPE IF EXISTS
            scraper_status_enum, scraper_source_enum, mover_type_enum,
            filing_type_enum, period_type_enum, exchange_enum;
        """
    )
