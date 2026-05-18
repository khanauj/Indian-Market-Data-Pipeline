"""APScheduler job definitions.

All jobs are async, market-hours-aware where applicable, and emit
Prometheus metrics + run-log rows via the scrapers' BaseScraper.run().
"""
from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from core.config import settings
from core.logging import get_logger

if TYPE_CHECKING:
    from scrapers.amfi import AMFIScraper
    from scrapers.bse import BSEScraper
    from scrapers.moneycontrol import MoneycontrolScraper
    from scrapers.nse import NSEScraper
    from scrapers.screener import ScreenerScraper

log = get_logger("scheduler")
IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


def is_market_hours(now: datetime | None = None) -> bool:
    """NSE/BSE equity market hours: 09:15–15:30 IST, Monday–Friday."""
    now = now or datetime.now(tz=IST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    else:
        now = now.astimezone(IST)
    if now.weekday() >= 5:  # 5=Sat, 6=Sun
        return False
    return MARKET_OPEN <= now.time() <= MARKET_CLOSE


def _market_hours_guard(coro_func):
    """Decorator: skip job (with log) outside market hours."""
    async def wrapper() -> None:
        if not is_market_hours():
            log.debug("skip_outside_market_hours", job=coro_func.__name__)
            return
        await coro_func()
    wrapper.__name__ = coro_func.__name__
    return wrapper


def build_scheduler(
    nse: "NSEScraper",
    bse: "BSEScraper",
    screener: "ScreenerScraper",
    moneycontrol: "MoneycontrolScraper",
    amfi: "AMFIScraper",
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=IST)

    # ─── Market-hours jobs (every 5 min) ────────────────────────────
    @_market_hours_guard
    async def job_prices() -> None:
        await nse.run("prices")

    @_market_hours_guard
    async def job_gainers_losers() -> None:
        await nse.run("gainers_losers")

    @_market_hours_guard
    async def job_indices() -> None:
        await nse.run("indices")

    scheduler.add_job(
        job_prices, IntervalTrigger(minutes=5), id="nse_prices", max_instances=1,
        coalesce=True, replace_existing=True,
    )
    scheduler.add_job(
        job_gainers_losers, IntervalTrigger(minutes=5), id="nse_gainers_losers",
        max_instances=1, coalesce=True, replace_existing=True,
    )
    scheduler.add_job(
        job_indices, IntervalTrigger(minutes=5), id="nse_indices",
        max_instances=1, coalesce=True, replace_existing=True,
    )

    # ─── News (every 10 min, runs anytime) ──────────────────────────
    async def job_news() -> None:
        await moneycontrol.run()

    scheduler.add_job(
        job_news, IntervalTrigger(minutes=10), id="mc_news",
        max_instances=1, coalesce=True, replace_existing=True,
    )

    # ─── Filings (every 15 min) ────────────────────────────────────
    async def job_filings() -> None:
        await bse.run("filings")

    scheduler.add_job(
        job_filings, IntervalTrigger(minutes=15), id="bse_filings",
        max_instances=1, coalesce=True, replace_existing=True,
    )

    # ─── Daily jobs ─────────────────────────────────────────────────
    async def job_amfi() -> None:
        await amfi.run()

    scheduler.add_job(
        job_amfi, CronTrigger(hour=7, minute=0, timezone=IST), id="amfi_nav",
        max_instances=1, coalesce=True, replace_existing=True,
    )

    async def job_financials() -> None:
        await screener.run()

    scheduler.add_job(
        job_financials, CronTrigger(hour=2, minute=0, timezone=IST), id="screener_fin",
        max_instances=1, coalesce=True, replace_existing=True,
    )

    async def job_master_sync() -> None:
        await bse.run("master")

    scheduler.add_job(
        job_master_sync, CronTrigger(hour=1, minute=0, timezone=IST), id="bse_master",
        max_instances=1, coalesce=True, replace_existing=True,
    )

    log.info(
        "scheduler_built",
        jobs=[j.id for j in scheduler.get_jobs()],
        tz=str(IST),
        market_hours_aware=True,
    )
    return scheduler
