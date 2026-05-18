"""APScheduler job definitions.

All jobs are async, market-hours-aware where applicable, and emit
Prometheus metrics + run-log rows via the scrapers' BaseScraper.run().

Schedule (IST):
- Market hours (5-min): NSE prices, gainers/losers, indices
- News every 30 min: Moneycontrol
- Corporate announcements hourly: BSE filings
- 18:00 daily: EOD batch (NSE prices snapshot, BSE EOD)
- 18:30 daily: AMFI NAV (after market close)
- 22:00 daily: Corporate actions
- 01:00 daily: BSE master refresh
- Sunday 02:00: Screener financial statements (quarterly cadence)
- 1st of Jan/Apr/Jul/Oct 03:00: Shareholding pattern (quarterly)
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

    # ═════════════════════════════════════════════════════════════════
    # INTRADAY — market-hours jobs (every 5 min)
    # ═════════════════════════════════════════════════════════════════
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
        job_prices, IntervalTrigger(minutes=5), id="nse_prices",
        max_instances=1, coalesce=True, replace_existing=True,
    )
    scheduler.add_job(
        job_gainers_losers, IntervalTrigger(minutes=5), id="nse_gainers_losers",
        max_instances=1, coalesce=True, replace_existing=True,
    )
    scheduler.add_job(
        job_indices, IntervalTrigger(minutes=5), id="nse_indices",
        max_instances=1, coalesce=True, replace_existing=True,
    )

    # ═════════════════════════════════════════════════════════════════
    # NEWS — every 30 minutes, 24/7
    # ═════════════════════════════════════════════════════════════════
    async def job_news() -> None:
        await moneycontrol.run()

    scheduler.add_job(
        job_news, IntervalTrigger(minutes=30), id="mc_news",
        max_instances=1, coalesce=True, replace_existing=True,
    )

    # ═════════════════════════════════════════════════════════════════
    # CORPORATE ANNOUNCEMENTS — hourly during business hours
    # ═════════════════════════════════════════════════════════════════
    async def job_announcements() -> None:
        await bse.run("filings")

    scheduler.add_job(
        job_announcements,
        CronTrigger(hour="9-18", minute=0, timezone=IST),
        id="bse_announcements", max_instances=1, coalesce=True, replace_existing=True,
    )

    # ═════════════════════════════════════════════════════════════════
    # EOD BATCH — daily 18:00 IST (after market close)
    # ═════════════════════════════════════════════════════════════════
    async def job_eod_batch() -> None:
        """Master EOD job — runs all end-of-day refreshes in sequence.

        Per user spec: triggered at 18:00 IST daily. Pulls latest data
        from all configured sources, detects changes, upserts to DB.
        Each sub-task is independent and idempotent — failure of one
        does not block others.
        """
        log.info("eod_batch_started", time=datetime.now(tz=IST).isoformat())
        results = {}

        for label, coro in [
            ("nse_prices_eod", nse.run("prices")),
            ("nse_gainers_losers", nse.run("gainers_losers")),
            ("nse_indices_eod", nse.run("indices")),
        ]:
            try:
                results[label] = await coro
            except Exception as e:  # noqa: BLE001
                log.error("eod_subtask_failed", task=label, error=str(e))
                results[label] = {"status": "failed", "error": str(e)}

        log.info("eod_batch_completed", results={k: v.get("status") for k, v in results.items()})

    scheduler.add_job(
        job_eod_batch,
        CronTrigger(hour=18, minute=0, day_of_week="mon-fri", timezone=IST),
        id="eod_batch_18", max_instances=1, coalesce=True, replace_existing=True,
    )

    # ═════════════════════════════════════════════════════════════════
    # AMFI NAV — daily 18:30 IST (after market close)
    # ═════════════════════════════════════════════════════════════════
    async def job_amfi() -> None:
        await amfi.run()

    scheduler.add_job(
        job_amfi,
        CronTrigger(hour=18, minute=30, timezone=IST),
        id="amfi_nav", max_instances=1, coalesce=True, replace_existing=True,
    )

    # ═════════════════════════════════════════════════════════════════
    # CORPORATE ACTIONS — daily 22:00 IST
    # ═════════════════════════════════════════════════════════════════
    async def job_corporate_actions() -> None:
        # BSE filings task captures dividends, splits, bonus, AGM, etc.
        await bse.run("filings")

    scheduler.add_job(
        job_corporate_actions,
        CronTrigger(hour=22, minute=0, timezone=IST),
        id="corporate_actions_daily",
        max_instances=1, coalesce=True, replace_existing=True,
    )

    # ═════════════════════════════════════════════════════════════════
    # BSE MASTER — daily 01:00 IST
    # ═════════════════════════════════════════════════════════════════
    async def job_master_sync() -> None:
        await bse.run("master")

    scheduler.add_job(
        job_master_sync,
        CronTrigger(hour=1, minute=0, timezone=IST),
        id="bse_master", max_instances=1, coalesce=True, replace_existing=True,
    )

    # ═════════════════════════════════════════════════════════════════
    # FINANCIAL STATEMENTS — quarterly (Sunday 02:00 IST, runs always
    # but Screener internally checks for new filings)
    # ═════════════════════════════════════════════════════════════════
    async def job_financials() -> None:
        await screener.run()

    scheduler.add_job(
        job_financials,
        CronTrigger(day_of_week="sun", hour=2, minute=0, timezone=IST),
        id="screener_financials",
        max_instances=1, coalesce=True, replace_existing=True,
    )

    # ═════════════════════════════════════════════════════════════════
    # SHAREHOLDING — quarterly (1st of Jan/Apr/Jul/Oct, 03:00 IST)
    # Shareholding pattern is filed within 21 days of quarter-end.
    # We poll on the 25th of Jan/Apr/Jul/Oct to give a buffer.
    # ═════════════════════════════════════════════════════════════════
    async def job_shareholding() -> None:
        # Screener exposes shareholding via the same financials scrape
        await screener.run()

    scheduler.add_job(
        job_shareholding,
        CronTrigger(month="1,4,7,10", day=25, hour=3, minute=0, timezone=IST),
        id="shareholding_quarterly",
        max_instances=1, coalesce=True, replace_existing=True,
    )

    log.info(
        "scheduler_built",
        jobs=[j.id for j in scheduler.get_jobs()],
        tz=str(IST),
        market_hours_aware=True,
    )
    return scheduler
