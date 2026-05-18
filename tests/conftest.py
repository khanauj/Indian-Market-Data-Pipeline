"""Shared pytest fixtures.

Tests are split into two flavors:
  • Pure unit tests — no DB, no network. Use a FakeDB instead of asyncpg.
  • Integration tests — marked @pytest.mark.integration, skipped by default.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("ENV", "test")
os.environ.setdefault("CACHE_ENABLED", "false")
os.environ.setdefault("SCHEDULER_ENABLED", "false")


@pytest.fixture
def fake_db() -> AsyncMock:
    """In-memory stand-in for DBService.

    Records calls to upsert_batch / execute / fetch for assertion.
    """
    db = AsyncMock()
    db.upserts = []  # type: ignore[attr-defined]

    async def _upsert_batch(
        table: str, rows: list[Any], conflict_cols: list[str], **kw: Any
    ) -> tuple[int, int]:
        db.upserts.append({"table": table, "rows": list(rows), "conflict_cols": list(conflict_cols)})
        return len(rows), 0

    db.upsert_batch.side_effect = _upsert_batch
    db.log_scraper_run.return_value = None
    db.update_checkpoint.return_value = None
    db.fetch.return_value = []
    db.fetchrow.return_value = None
    db.fetchval.return_value = None
    db.health.return_value = {"ok": True}
    db.get_symbols_for_scraping.return_value = []
    return db


@pytest.fixture
def now_utc() -> datetime:
    return datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
