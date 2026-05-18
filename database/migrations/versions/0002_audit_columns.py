"""Add audit columns (source_name, last_refresh_time, data_version) to key tables.

Revision ID: 0002_audit_columns
Revises: 0001_initial
Create Date: 2026-05-18

Adds three audit columns to tables that ingest from external sources:
  - source_name        TEXT       — Origin source identifier (e.g. 'nse', 'bse', 'amfi')
  - last_refresh_time  TIMESTAMPTZ — When this row was last refreshed from source
  - data_version       INTEGER    — Incremented on every UPDATE for change tracking

Existing rows are backfilled with source_name='legacy' and data_version=1.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_audit_columns"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


# Tables that should carry source attribution + version tracking.
# Operational tables (scraper_run_log, etc.) are intentionally excluded.
AUDITED_TABLES = [
    "stocks_master",
    "stock_prices",
    "mutual_funds",
    "market_indices",
    "top_gainers_losers",
    "company_filings",
    "company_news",
    "financials",
]


def upgrade() -> None:
    for table in AUDITED_TABLES:
        # Skip if table doesn't exist (defensive)
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        if table not in inspector.get_table_names():
            continue

        existing_cols = {c["name"] for c in inspector.get_columns(table)}

        if "source_name" not in existing_cols:
            op.add_column(table, sa.Column("source_name", sa.Text(), nullable=True))
            op.execute(f"UPDATE {table} SET source_name = 'legacy' WHERE source_name IS NULL")

        if "last_refresh_time" not in existing_cols:
            op.add_column(
                table,
                sa.Column(
                    "last_refresh_time",
                    sa.TIMESTAMP(timezone=True),
                    nullable=True,
                    server_default=sa.text("NOW()"),
                ),
            )
            op.execute(f"UPDATE {table} SET last_refresh_time = COALESCE(updated_at, NOW())")

        if "data_version" not in existing_cols:
            op.add_column(
                table,
                sa.Column("data_version", sa.Integer(), nullable=False, server_default="1"),
            )

    # Index for filtering by source efficiently
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_stocks_master_source
        ON stocks_master(source_name) WHERE source_name IS NOT NULL;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mutual_funds_source
        ON mutual_funds(source_name) WHERE source_name IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_stocks_master_source")
    op.execute("DROP INDEX IF EXISTS idx_mutual_funds_source")

    for table in AUDITED_TABLES:
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        if table not in inspector.get_table_names():
            continue
        existing_cols = {c["name"] for c in inspector.get_columns(table)}
        for col in ("data_version", "last_refresh_time", "source_name"):
            if col in existing_cols:
                op.drop_column(table, col)
