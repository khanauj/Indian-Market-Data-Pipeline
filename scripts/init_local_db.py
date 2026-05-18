"""Create the local SQLite database and apply the schema.

Usage:
    python -m scripts.init_local_db                       # default path from settings
    python -m scripts.init_local_db --path data/dev.sqlite
    python -m scripts.init_local_db --force               # drop existing file first
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from core.config import settings
from core.logging import configure_logging, get_logger
from services.sqlite_storage import SQLiteStorage

log = get_logger("init_local_db")


async def main(path: str, force: bool) -> None:
    target = Path(path)
    if force and target.exists() and path != ":memory:":
        target.unlink()
        log.info("dropped_existing_file", path=path)

    storage = SQLiteStorage(path=path)
    await storage.connect()

    # Sanity check
    health = await storage.health()
    log.info("db_initialized", path=path, health=health)

    # Confirm the schema actually landed
    row = await storage.fetchrow(
        "SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table'"
    )
    log.info("tables_present", count=row["n"] if row else 0)

    await storage.close()


if __name__ == "__main__":
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default=settings.sqlite_path)
    parser.add_argument("--force", action="store_true",
                        help="Delete existing DB file before initializing")
    args = parser.parse_args()
    asyncio.run(main(args.path, args.force))
