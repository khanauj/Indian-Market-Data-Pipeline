"""SQLite storage backend.

Implements the same upsert_batch / fetch / fetchrow / fetchval / execute
interface as DBService (Postgres) so the rest of the pipeline doesn't
need to know which backend is active.

Notes
-----
• Parameter style: aiosqlite uses '?' placeholders. We translate
  asyncpg-style '$1, $2, ...' on the way in so router SQL stays portable.
• Schema is applied on first connect() if the target tables don't exist.
• datetime objects are stored as ISO-8601 strings; aiosqlite returns
  TEXT, so consumers should `datetime.fromisoformat()` where typed.
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiosqlite
from pydantic import BaseModel

from core.config import settings
from core.exceptions import DatabaseException
from core.logging import get_logger
from models.enums import ScraperSource, ScraperStatus

log = get_logger("sqlite")

_PG_PARAM_RE = re.compile(r"\$(\d+)")
_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "database" / "schema_sqlite.sql"


def _pg_to_sqlite_params(query: str) -> str:
    """Translate $1, $2, ... → ?, ?, ... while preserving param order."""
    return _PG_PARAM_RE.sub("?", query)


def _encode_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bytes)):
        return value
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return str(value)


def _model_to_row(m: BaseModel) -> dict[str, Any]:
    return m.model_dump(mode="python", exclude_none=False)


class _SQLiteRow(dict):
    """Lets routers do `row["col"]` like asyncpg.Record does."""


# Columns whose TEXT contents are JSON; SQLiteStorage.fetch() will decode them.
_JSON_COLUMNS = frozenset({"raw_payload"})


def _decode_row_json(row: dict[str, Any]) -> dict[str, Any]:
    for col in _JSON_COLUMNS & row.keys():
        v = row[col]
        if isinstance(v, str) and v:
            try:
                row[col] = json.loads(v)
            except json.JSONDecodeError:
                pass  # leave as-is; caller can decide
    return row


class SQLiteStorage:
    def __init__(self, path: str | None = None) -> None:
        self._path = path or settings.sqlite_path
        self._conn: aiosqlite.Connection | None = None

    # ─── Lifecycle ──────────────────────────────────────────────────
    async def connect(self) -> None:
        if self._conn is not None:
            return
        if self._path not in (":memory:", "file::memory:?cache=shared"):
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._conn.execute("PRAGMA journal_mode = WAL")
        await self._conn.execute("PRAGMA synchronous = NORMAL")
        await self._apply_schema_if_empty()
        await self._conn.commit()
        log.info("sqlite_connected", path=self._path)

    async def _apply_schema_if_empty(self) -> None:
        assert self._conn is not None
        cur = await self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='stocks_master'"
        )
        existing = await cur.fetchone()
        await cur.close()
        if existing:
            return
        if not _SCHEMA_PATH.exists():
            raise DatabaseException("schema_sqlite.sql not found", path=str(_SCHEMA_PATH))
        sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        await self._conn.executescript(sql)
        log.info("sqlite_schema_applied")

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def health(self) -> dict[str, Any]:
        if self._conn is None:
            return {"ok": False, "reason": "not_connected"}
        try:
            cur = await self._conn.execute("SELECT 1 AS one")
            row = await cur.fetchone()
            await cur.close()
            return {"ok": row is not None and row["one"] == 1, "backend": "sqlite", "path": self._path}
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
        if not rows or self._conn is None:
            if self._conn is None:
                raise DatabaseException("sqlite not connected")
            return 0, 0

        normalized: list[dict[str, Any]] = []
        for r in rows:
            d = _model_to_row(r) if isinstance(r, BaseModel) else dict(r)
            for col in jsonb_cols:
                if col in d and d[col] is not None:
                    d[col] = json.dumps(d[col], default=str)
            normalized.append(d)

        cols = list(normalized[0].keys())
        placeholders = ", ".join("?" for _ in cols)
        col_list = ", ".join(f'"{c}"' for c in cols)
        conflict_list = ", ".join(f'"{c}"' for c in conflict_cols)

        if update_cols is None:
            update_cols = [c for c in cols if c not in conflict_cols and c != "id"]

        if update_cols:
            set_clause = ", ".join(f'"{c}" = excluded."{c}"' for c in update_cols)
            on_conflict = f"ON CONFLICT ({conflict_list}) DO UPDATE SET {set_clause}"
        else:
            on_conflict = f"ON CONFLICT ({conflict_list}) DO NOTHING"

        sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) {on_conflict}'
        values_iter = [tuple(_encode_value(r.get(c)) for c in cols) for r in normalized]

        try:
            await self._conn.executemany(sql, values_iter)
            await self._conn.commit()
        except aiosqlite.Error as e:
            await self._conn.rollback()
            raise DatabaseException(
                "sqlite upsert failed", table=table, error=str(e), rows=len(rows)
            ) from e

        return len(rows), 0

    # ─── Query helpers ──────────────────────────────────────────────
    async def fetch(self, query: str, *args: Any) -> list[_SQLiteRow]:
        assert self._conn is not None
        q = _pg_to_sqlite_params(query)
        cur = await self._conn.execute(q, [_encode_value(a) for a in args])
        rows = await cur.fetchall()
        await cur.close()
        return [
            _SQLiteRow(_decode_row_json(dict(zip(r.keys(), tuple(r), strict=False))))
            for r in rows
        ]

    async def fetchrow(self, query: str, *args: Any) -> _SQLiteRow | None:
        rows = await self.fetch(query, *args)
        return rows[0] if rows else None

    async def fetchval(self, query: str, *args: Any) -> Any:
        row = await self.fetchrow(query, *args)
        if row is None:
            return None
        return next(iter(row.values()))

    async def execute(self, query: str, *args: Any) -> str:
        assert self._conn is not None
        q = _pg_to_sqlite_params(query)
        await self._conn.execute(q, [_encode_value(a) for a in args])
        await self._conn.commit()
        return "OK"

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
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            source.value, status.value, records_inserted, records_skipped,
            error_msg, started_at.isoformat(), ended_at.isoformat(),
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
            VALUES (?, ?, ?, ?)
            ON CONFLICT (source) DO UPDATE SET
                last_run_at     = excluded.last_run_at,
                last_success_at = COALESCE(excluded.last_success_at, scraper_checkpoints.last_success_at),
                cursor_value    = COALESCE(excluded.cursor_value, scraper_checkpoints.cursor_value),
                updated_at      = strftime('%Y-%m-%dT%H:%M:%fZ','now')
            """,
            source.value,
            last_run_at.isoformat(),
            last_success_at.isoformat() if last_success_at else None,
            cursor_value,
        )

    async def get_symbols_for_scraping(
        self, limit: int, max_age_hours: int = 24
    ) -> list[str]:
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
        rows = await self.fetch(
            """
            SELECT sm.symbol
            FROM stocks_master sm
            LEFT JOIN (
                SELECT symbol, MAX(scraped_at) AS last_scraped
                FROM financials GROUP BY symbol
            ) f ON f.symbol = sm.symbol
            WHERE sm.is_active = 1
              AND (f.last_scraped IS NULL OR f.last_scraped < ?)
            ORDER BY f.last_scraped IS NOT NULL, f.last_scraped
            LIMIT ?
            """,
            cutoff, limit,
        )
        return [r["symbol"] for r in rows]
