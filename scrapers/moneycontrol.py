"""Moneycontrol scraper — company news via Playwright.

Moneycontrol's article pages are JS-heavy and bot-checked. We use a
shared Playwright context, drive it through symbol_slug_map.mc_slug, and
deduplicate news on SHA256(url).
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any, ClassVar

from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

try:
    from playwright_stealth import stealth_async  # type: ignore[import-untyped]
except ImportError:
    stealth_async = None  # type: ignore[assignment]

from core.config import settings
from core.exceptions import AntibotBlockError
from models.enums import ScraperSource
from models.schemas import CompanyNewsIn
from scrapers.base import BaseScraper
from services.normalization import normalize_datetime

NEWS_URL_TMPL = "https://www.moneycontrol.com/company-article/{slug}/news/{mc_code}"


class MoneycontrolScraper(BaseScraper):
    source: ClassVar[ScraperSource] = ScraperSource.MONEYCONTROL

    def __init__(self, *a: Any, **kw: Any) -> None:
        super().__init__(*a, **kw)
        self._pw = None
        self._browser: Browser | None = None
        self._ctx: BrowserContext | None = None

    async def _ensure_browser(self) -> BrowserContext:
        if self._ctx is not None:
            return self._ctx
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=settings.playwright_headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._ctx = await self._browser.new_context(
            locale=settings.playwright_locale,
            timezone_id=settings.playwright_timezone,
            viewport={
                "width": settings.playwright_viewport_width,
                "height": settings.playwright_viewport_height,
            },
        )
        return self._ctx

    async def stop(self) -> None:
        await super().stop()
        if self._ctx is not None:
            await self._ctx.close()
            self._ctx = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._pw is not None:
            await self._pw.stop()
            self._pw = None

    # ═══════════════════════════════════════════════════════════════
    # Fetch
    # ═══════════════════════════════════════════════════════════════
    async def fetch(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        rows = await self.db.fetch(
            """
            SELECT m.nse_symbol AS symbol, m.mc_slug, m.bse_code
            FROM symbol_slug_map m
            WHERE m.mc_slug IS NOT NULL
            ORDER BY m.updated_at NULLS FIRST
            LIMIT 100
            """
        )
        if not rows:
            self.log.info("no_slugs_to_scrape")
            return []

        ctx = await self._ensure_browser()
        sem = asyncio.Semaphore(min(3, settings.scraper_concurrency))
        out: list[dict[str, Any]] = []

        async def _one(r: Any) -> None:
            async with sem:
                try:
                    articles = await self._scrape_company_news(
                        ctx, symbol=r["symbol"], slug=r["mc_slug"], bse_code=r["bse_code"]
                    )
                    out.extend(articles)
                except AntibotBlockError:
                    self.log.warning("mc_blocked", symbol=r["symbol"])
                    await asyncio.sleep(30)
                except Exception as e:  # noqa: BLE001
                    self.log.warning("mc_company_failed", symbol=r["symbol"], error=str(e))

        await asyncio.gather(*(_one(r) for r in rows))
        return out

    async def _scrape_company_news(
        self, ctx: BrowserContext, *, symbol: str, slug: str, bse_code: str | None
    ) -> list[dict[str, Any]]:
        url = NEWS_URL_TMPL.format(slug=slug, mc_code=bse_code or slug)
        page: Page = await ctx.new_page()
        if stealth_async is not None:
            await stealth_async(page)
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            if resp is None or resp.status in (403, 503):
                raise AntibotBlockError("mc forbidden", status=resp.status if resp else None)
            await page.wait_for_selector("ul.news_list, .article_box, .news-list", timeout=15_000)
            html = await page.content()
        finally:
            await page.close()

        soup = BeautifulSoup(html, "lxml")
        articles: list[dict[str, Any]] = []
        # Moneycontrol's news listing markup uses several variants over time.
        nodes = (
            soup.select("ul.news_list li")
            or soup.select(".article_box")
            or soup.select(".news-list .article")
        )
        for n in nodes[:50]:
            link_el = n.select_one("a[href]")
            headline_el = n.select_one("h2") or n.select_one("a")
            time_el = n.select_one("time, .ago, .date")
            if not link_el or not headline_el:
                continue
            full_url = link_el["href"]
            if isinstance(full_url, list):
                full_url = full_url[0] if full_url else ""
            if not str(full_url).startswith("http"):
                full_url = f"https://www.moneycontrol.com{full_url}"
            published = normalize_datetime(
                time_el.get_text(strip=True) if time_el else None
            ) or datetime.now(tz=timezone.utc)
            articles.append({
                "symbol": symbol,
                "headline": headline_el.get_text(strip=True),
                "full_url": str(full_url),
                "url_hash": hashlib.sha256(str(full_url).encode()).hexdigest(),
                "source": "moneycontrol",
                "published_at": published,
            })
        return articles

    # ═══════════════════════════════════════════════════════════════
    # Normalize
    # ═══════════════════════════════════════════════════════════════
    async def normalize(self, raw: list[dict[str, Any]]) -> list[CompanyNewsIn]:
        out: list[CompanyNewsIn] = []
        now = datetime.now(tz=timezone.utc)
        seen: set[str] = set()
        for r in raw:
            h = r["url_hash"]
            if h in seen:
                continue
            seen.add(h)
            try:
                out.append(CompanyNewsIn(
                    symbol=r["symbol"],
                    headline=r["headline"],
                    url_hash=h,
                    full_url=r["full_url"],
                    source=r["source"],
                    summary=None,
                    sentiment=None,
                    published_at=r["published_at"],
                    scraped_at=now,
                ))
            except Exception:  # noqa: BLE001
                self.log.warning("mc_row_skipped", url=r.get("full_url"), exc_info=False)
        return out

    async def save(self, records: list[CompanyNewsIn]) -> tuple[int, int]:
        if not records:
            return 0, 0
        ins, _ = await self.db.upsert_batch(
            "company_news", records,
            conflict_cols=["url_hash"],
            update_cols=[],  # never update; first scrape wins
        )
        return ins, 0
