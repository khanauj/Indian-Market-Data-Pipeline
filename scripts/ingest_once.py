"""Run a single scraper end-to-end against the local SQLite DB.

Usage:
    python -m scripts.ingest_once amfi
    python -m scripts.ingest_once nse --task prices
    python -m scripts.ingest_once nse --task gainers_losers
    python -m scripts.ingest_once bse --task master
    python -m scripts.ingest_once screener

This is the fastest way to verify your local pipeline works without
booting the API or scheduler.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from core.logging import configure_logging, get_logger
from scrapers import (
    AMFIScraper,
    BSEScraper,
    MoneycontrolScraper,
    NSEScraper,
    ScreenerScraper,
)
from services.storage import get_storage

log = get_logger("ingest_once")

_SCRAPERS = {
    "amfi": AMFIScraper,
    "nse": NSEScraper,
    "bse": BSEScraper,
    "screener": ScreenerScraper,
    "moneycontrol": MoneycontrolScraper,
}


async def main(name: str, task: str | None) -> int:
    if name not in _SCRAPERS:
        log.error("unknown_scraper", name=name, available=list(_SCRAPERS))
        return 2

    storage = get_storage()
    await storage.connect()
    scraper = _SCRAPERS[name](storage)

    try:
        result = await (scraper.run(task) if task else scraper.run())
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "success" else 1
    finally:
        await scraper.stop()
        await storage.close()


if __name__ == "__main__":
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("scraper", choices=list(_SCRAPERS))
    parser.add_argument("--task", default=None,
                        help="Optional task argument (e.g. 'prices', 'master')")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.scraper, args.task)))
