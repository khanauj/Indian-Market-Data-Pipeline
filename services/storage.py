"""Storage protocol + backend factory.

The pipeline depends on `Storage`, not on a concrete database. Two
backends ship today:
    • PostgresStorage (asyncpg, Supabase-compatible) → services/db_service.py
    • SQLiteStorage   (aiosqlite, local file)        → services/sqlite_storage.py

The active backend is selected via $STORAGE_BACKEND. Callers should obtain
the backend via `get_storage()` — it returns the configured instance and
is the single point of switching.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from core.config import settings
from core.logging import get_logger
from models.enums import ScraperSource, ScraperStatus

log = get_logger("storage")


@runtime_checkable
class Storage(Protocol):
    """Common contract for every storage backend."""

    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def health(self) -> dict[str, Any]: ...

    async def upsert_batch(
        self,
        table: str,
        rows: Sequence[BaseModel] | Sequence[dict[str, Any]],
        conflict_cols: Sequence[str],
        update_cols: Sequence[str] | None = None,
        jsonb_cols: Sequence[str] = (),
    ) -> tuple[int, int]: ...

    async def fetch(self, query: str, *args: Any) -> list[Any]: ...
    async def fetchrow(self, query: str, *args: Any) -> Any: ...
    async def fetchval(self, query: str, *args: Any) -> Any: ...
    async def execute(self, query: str, *args: Any) -> Any: ...

    async def log_scraper_run(
        self,
        source: ScraperSource,
        status: ScraperStatus,
        started_at: datetime,
        ended_at: datetime,
        records_inserted: int = 0,
        records_skipped: int = 0,
        error_msg: str | None = None,
    ) -> None: ...

    async def update_checkpoint(
        self,
        source: ScraperSource,
        last_run_at: datetime,
        last_success_at: datetime | None = None,
        cursor_value: str | None = None,
    ) -> None: ...

    async def get_symbols_for_scraping(
        self, limit: int, max_age_hours: int = 24
    ) -> list[str]: ...


# ─── Factory ────────────────────────────────────────────────────────
_storage: Storage | None = None


def get_storage() -> Storage:
    """Return the active backend, instantiating it lazily."""
    global _storage
    if _storage is not None:
        return _storage

    backend = settings.storage_backend
    if backend == "sqlite":
        from services.sqlite_storage import SQLiteStorage
        _storage = SQLiteStorage()
    elif backend == "supabase":
        from services.db_service import DBService
        _storage = DBService()
    elif backend == "both":
        from services.db_service import DBService
        from services.sqlite_storage import SQLiteStorage
        _storage = TeeStorage(primary=DBService(), secondary=SQLiteStorage())
    else:
        raise ValueError(f"unknown STORAGE_BACKEND: {backend}")

    log.info("storage_backend_selected", backend=backend)
    return _storage


def set_storage(s: Storage) -> None:
    global _storage
    _storage = s


def reset_storage() -> None:
    """Test helper — drops the cached singleton."""
    global _storage
    _storage = None


# ─── Tee (used when STORAGE_BACKEND=both) ──────────────────────────
class TeeStorage:
    """Writes go to both backends. Reads come from the primary.

    A failure on the secondary is logged but does NOT abort the primary.
    """

    def __init__(self, primary: Storage, secondary: Storage) -> None:
        self.primary = primary
        self.secondary = secondary

    async def connect(self) -> None:
        await self.primary.connect()
        try:
            await self.secondary.connect()
        except Exception as e:  # noqa: BLE001
            log.warning("tee_secondary_connect_failed", error=str(e))

    async def close(self) -> None:
        await self.primary.close()
        try:
            await self.secondary.close()
        except Exception:  # noqa: BLE001
            pass

    async def health(self) -> dict[str, Any]:
        p = await self.primary.health()
        try:
            s = await self.secondary.health()
        except Exception as e:  # noqa: BLE001
            s = {"ok": False, "reason": str(e)}
        return {"ok": p.get("ok", False), "primary": p, "secondary": s}

    async def upsert_batch(
        self, table, rows, conflict_cols, update_cols=None, jsonb_cols=(),
    ):
        ins, skip = await self.primary.upsert_batch(
            table, rows, conflict_cols, update_cols, jsonb_cols
        )
        try:
            await self.secondary.upsert_batch(table, rows, conflict_cols, update_cols, jsonb_cols)
        except Exception as e:  # noqa: BLE001
            log.warning("tee_secondary_upsert_failed", table=table, error=str(e))
        return ins, skip

    async def fetch(self, query, *args):       return await self.primary.fetch(query, *args)
    async def fetchrow(self, query, *args):    return await self.primary.fetchrow(query, *args)
    async def fetchval(self, query, *args):    return await self.primary.fetchval(query, *args)
    async def execute(self, query, *args):     return await self.primary.execute(query, *args)

    async def log_scraper_run(self, *args, **kw):
        await self.primary.log_scraper_run(*args, **kw)
        try:
            await self.secondary.log_scraper_run(*args, **kw)
        except Exception:  # noqa: BLE001
            pass

    async def update_checkpoint(self, *args, **kw):
        await self.primary.update_checkpoint(*args, **kw)
        try:
            await self.secondary.update_checkpoint(*args, **kw)
        except Exception:  # noqa: BLE001
            pass

    async def get_symbols_for_scraping(self, limit, max_age_hours=24):
        return await self.primary.get_symbols_for_scraping(limit, max_age_hours)
