"""Async PostgreSQL service.

Uses asyncpg pool directly (faster, lighter than SQLAlchemy for hot-path
inserts). Supabase-compatible: works against the Supavisor pooler
(port 6543) or direct connection (port 5432).

All write helpers are idempotent (ON CONFLICT ... DO UPDATE).
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator

import asyncpg
from pydantic import BaseModel

from core.config import settings
from core.exceptions import DatabaseException
from core.logging import get_logger
from models.enums import ScraperSource, ScraperStatus

log = get_logger("db")


def _encode_jsonb(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, default=str)


def _model_to_row(m: BaseModel) -> dict[str, Any]:
    """Pydantic v2 dump that drops None and serializes JSONB fields."""
    return m.model_dump(mode="python", exclude_none=False)


class DBService:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    # ─── Lifecycle ──────────────────────────────────────────────────
    async def connect(self) -> None:
        if self._pool is not None:
            return
        try:
            self._pool = await asyncpg.create_pool(
                dsn=settings.database_url_str,
                min_size=settings.database_pool_min,
                max_size=settings.database_pool_max,
                command_timeout=30,
                init=_register_codecs,
                # Supabase pooler is statement-mode by default — disable prepared statements
                statement_cache_size=0,
            )
            log.info("db_pool_ready", min=settings.database_pool_min, max=settings.database_pool_max)
        except Exception as e:  # noqa: BLE001
            raise DatabaseException("db pool init failed", error=str(e)) from e

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        if self._pool is None:
            raise DatabaseException("db pool not initialized")
        async with self._pool.acquire() as conn:
            yield conn

    async def health(self) -> dict[str, Any]:
        if self._pool is None:
            return {"ok": False, "reason": "pool_not_initialized"}
        try:
            async with self.acquire() as conn:
                row = await conn.fetchrow("SELECT 1 AS one")
            return {"ok": row is not None and row["one"] == 1}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "reason": str(e)}

    # ─── Generic UPSERT ─────────────────────────────────────────────
    async def upsert_batch(
        self,
        table: str,
        rows: Sequence[BaseModel] | Sequence[dict[str, Any]],
        conflict_cols: Sequence[str],
        update_cols: Sequence[str] | None = None,
        jsonb_cols: Sequence[str] = (),
    ) -> tuple[int, int]:
        """Bulk INSERT ... ON CONFLICT (conflict_cols) DO UPDATE SET ...

        Returns (inserted_or_updated, skipped). Skipped is best-effort —
        Postgres ON CONFLICT doesn't distinguish insert vs update by default,
        so we count rows the executemany affected.
        """
        if not rows:
            return 0, 0

        normalized: list[dict[str, Any]] = []
        for r in rows:
            d = _model_to_row(r) if isinstance(r, BaseModel) else dict(r)
            for col in jsonb_cols:
                if col in d:
                    d[col] = _encode_jsonb(d[col])
            normalized.append(d)

        cols = list(normalized[0].keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(cols)))
        col_list = ", ".join(f'"{c}"' for c in cols)
        conflict_list = ", ".join(f'"{c}"' for c in conflict_cols)

        if update_cols is None:
            update_cols = [c for c in cols if c not in conflict_cols and c != "id"]

        if update_cols:
            set_clause = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)
            on_conflict = f"ON CONFLICT ({conflict_list}) DO UPDATE SET {set_clause}"
        else:
            on_conflict = f"ON CONFLICT ({conflict_list}) DO NOTHING"

        sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) {on_conflict}'

        values_iter = [[r[c] for c in cols] for r in normalized]

        async with self.acquire() as conn:
            async with conn.transaction():
                try:
                    await conn.executemany(sql, values_iter)
                except asyncpg.PostgresError as e:
                    raise DatabaseException(
                        "upsert failed", table=table, error=str(e), rows=len(rows)
                    ) from e

        return len(rows), 0

    # ─── Query helpers ──────────────────────────────────────────────
    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        async with self.acquire() as conn:
            return await conn.execute(query, *args)

    # ─── Operational helpers ────────────────────────────────────────
    async def log_scraper_run(
        self,
        source: ScraperSource,
        status: ScraperStatus,
        started_at: datetime,
        ended_at: datetime,
        records_inserted: int = 0,
        records_skipped: int = 0,
        error_msg: str | None = None,
    ) -> None:
        await self.execute(
            """
            INSERT INTO scraper_run_log
                (source, status, records_inserted, records_skipped, error_msg, started_at, ended_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            source.value, status.value, records_inserted, records_skipped,
            error_msg, started_at, ended_at,
        )

    async def update_checkpoint(
        self,
        source: ScraperSource,
        last_run_at: datetime,
        last_success_at: datetime | None = None,
        cursor_value: str | None = None,
    ) -> None:
        await self.execute(
            """
            INSERT INTO scraper_checkpoints (source, last_run_at, last_success_at, cursor_value)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (source) DO UPDATE SET
                last_run_at     = EXCLUDED.last_run_at,
                last_success_at = COALESCE(EXCLUDED.last_success_at, scraper_checkpoints.last_success_at),
                cursor_value    = COALESCE(EXCLUDED.cursor_value, scraper_checkpoints.cursor_value)
            """,
            source.value, last_run_at, last_success_at, cursor_value,
        )

    async def get_symbols_for_scraping(
        self, limit: int, max_age_hours: int = 24
    ) -> list[str]:
        """Return symbols whose financials haven't been refreshed in N hours."""
        rows = await self.fetch(
            """
            SELECT sm.symbol
            FROM stocks_master sm
            LEFT JOIN LATERAL (
                SELECT MAX(scraped_at) AS last_scraped
                FROM financials f
                WHERE f.symbol = sm.symbol
            ) f ON TRUE
            WHERE sm.is_active = TRUE
              AND (f.last_scraped IS NULL OR f.last_scraped < now() - ($1 || ' hours')::INTERVAL)
            ORDER BY f.last_scraped NULLS FIRST
            LIMIT $2
            """,
            str(max_age_hours), limit,
        )
        return [r["symbol"] for r in rows]


# ─── Codec registration ────────────────────────────────────────────
async def _register_codecs(conn: asyncpg.Connection) -> None:
    # JSONB as raw Python objects in / JSON-string out (we encode ourselves)
    await conn.set_type_codec(
        "jsonb", encoder=str, decoder=json.loads, schema="pg_catalog", format="text"
    )
    await conn.set_type_codec(
        "json", encoder=str, decoder=json.loads, schema="pg_catalog", format="text"
    )


# ─── Compat layer ──────────────────────────────────────────────────
# Legacy callers used to import get_db()/set_db() directly from this module.
# Those now delegate to services.storage so the backend stays uniform.
def get_db() -> Any:
    from services.storage import get_storage
    return get_storage()


def set_db(db: Any) -> None:
    from services.storage import set_storage
    set_storage(db)
