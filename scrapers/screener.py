"""Screener.in scraper — Playwright + BS4 for financial statements.

Workflow:
  1. Pick batch of symbols whose financials are >24h stale.
  2. For each, navigate to https://www.screener.in/company/{SYMBOL}/
  3. Parse #profit-loss, #balance-sheet, #cash-flow + sidebar ratios.
  4. UPSERT into financials. On Cloudflare block: rotate proxy + retry.

Selectors are pinned to Screener's section IDs that have been stable for
2+ years. If the page layout changes, only this scraper needs updates.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any, ClassVar

from bs4 import BeautifulSoup
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
)

try:
    from playwright_stealth import stealth_async  # type: ignore[import-untyped]
except ImportError:
    stealth_async = None  # type: ignore[assignment]

from core.config import settings
from core.exceptions import AntibotBlockError
from models.enums import PeriodType, ScraperSource
from models.schemas import FinancialsIn
from scrapers.base import BaseScraper
from services.normalization import normalize_currency_cr, normalize_percentage

SCREENER_BASE = "https://www.screener.in/company"
_CR = 1e7


class ScreenerScraper(BaseScraper):
    source: ClassVar[ScraperSource] = ScraperSource.SCREENER

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
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
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
        symbols: list[str] = kwargs.get("symbols") or await self.db.get_symbols_for_scraping(
            limit=settings.screener_batch_size, max_age_hours=24
        )
        if not symbols:
            return []
        self.log.info("screener_batch", count=len(symbols))

        ctx = await self._ensure_browser()
        out: list[dict[str, Any]] = []
        sem = asyncio.Semaphore(min(3, settings.scraper_concurrency))

        async def _one(sym: str) -> None:
            async with sem:
                try:
                    out.append(await self._scrape_company(ctx, sym))
                except AntibotBlockError:
                    self.log.warning("screener_blocked", symbol=sym)
                    await asyncio.sleep(30)
                except Exception as e:  # noqa: BLE001
                    self.log.warning("screener_company_failed", symbol=sym, error=str(e))

        await asyncio.gather(*(_one(s) for s in symbols))
        return out

    async def _scrape_company(self, ctx: BrowserContext, symbol: str) -> dict[str, Any]:
        url = f"{SCREENER_BASE}/{symbol}/"
        page: Page = await ctx.new_page()
        if stealth_async is not None:
            await stealth_async(page)
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            if resp is None or resp.status >= 500:
                raise AntibotBlockError("screener bad response", status=resp.status if resp else None)
            if resp.status in (403, 503):
                raise AntibotBlockError("screener forbidden", status=resp.status)

            await page.wait_for_selector("#top-ratios", timeout=20_000)
            html = await page.content()
        finally:
            await page.close()

        return self._parse_company_page(symbol, html)

    # ═══════════════════════════════════════════════════════════════
    # Parse
    # ═══════════════════════════════════════════════════════════════
    def _parse_company_page(self, symbol: str, html: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        ratios = self._extract_top_ratios(soup)
        quarterly = self._extract_table(soup, "#quarters")
        annual = self._extract_table(soup, "#profit-loss")
        bs = self._extract_table(soup, "#balance-sheet")
        cf = self._extract_table(soup, "#cash-flow")
        shareholding = self._extract_shareholding(soup)

        return {
            "symbol": symbol,
            "ratios": ratios,
            "quarterly": quarterly,
            "annual": annual,
            "balance_sheet": bs,
            "cash_flow": cf,
            "shareholding": shareholding,
        }

    @staticmethod
    def _extract_top_ratios(soup: BeautifulSoup) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for li in soup.select("#top-ratios li"):
            name_el = li.select_one(".name")
            val_el = li.select_one(".value")
            if not name_el or not val_el:
                continue
            key = name_el.get_text(strip=True).lower().replace(" ", "_")
            out[key] = val_el.get_text(" ", strip=True)
        return out

    @staticmethod
    def _extract_table(soup: BeautifulSoup, selector: str) -> dict[str, dict[str, str]]:
        """Return {row_label: {column_label: cell_text}}."""
        section = soup.select_one(selector)
        if not section:
            return {}
        table = section.find("table")
        if not table:
            return {}
        headers = [th.get_text(strip=True) for th in table.select("thead th")][1:]  # drop label col
        out: dict[str, dict[str, str]] = {}
        for tr in table.select("tbody tr"):
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue
            label = cells[0].get_text(strip=True)
            values = [c.get_text(strip=True) for c in cells[1:]]
            out[label] = dict(zip(headers, values, strict=False))
        return out

    @staticmethod
    def _extract_shareholding(soup: BeautifulSoup) -> dict[str, float | None]:
        section = soup.select_one("#shareholding")
        if not section:
            return {}
        out: dict[str, float | None] = {}
        table = section.find("table")
        if not table:
            return out
        latest_header_idx = -1  # last column = most recent
        for tr in table.select("tbody tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            key = cells[0].get_text(strip=True).lower()
            val = cells[latest_header_idx].get_text(strip=True)
            out[key] = normalize_percentage(val)
        return out

    # ═══════════════════════════════════════════════════════════════
    # Normalize
    # ═══════════════════════════════════════════════════════════════
    async def normalize(self, raw: list[dict[str, Any]]) -> list[FinancialsIn]:
        out: list[FinancialsIn] = []
        for company in raw:
            sym = company.get("symbol")
            if not sym:
                continue
            ratios = company.get("ratios", {})
            quarterly = company.get("quarterly", {})
            annual = company.get("annual", {})
            cf = company.get("cash_flow", {})

            # Quarterly rows (last 8 columns of #quarters)
            for period_label, period_end in self._period_labels(quarterly, kind="Q"):
                out.append(self._build_financials(
                    symbol=sym,
                    period_type=PeriodType.QUARTERLY,
                    period_end_date=period_end,
                    table_q=quarterly, table_a=annual, table_cf=cf,
                    period_label=period_label, ratios=ratios,
                ))
            # Annual rows
            for period_label, period_end in self._period_labels(annual, kind="A"):
                out.append(self._build_financials(
                    symbol=sym,
                    period_type=PeriodType.ANNUAL,
                    period_end_date=period_end,
                    table_q=quarterly, table_a=annual, table_cf=cf,
                    period_label=period_label, ratios=ratios,
                ))
        return out

    @staticmethod
    def _period_labels(
        table: dict[str, dict[str, str]], kind: str
    ) -> list[tuple[str, date]]:
        """Extract sorted period (label, date) pairs from a Screener table."""
        if not table:
            return []
        first_row = next(iter(table.values()))
        labels = list(first_row.keys())
        out: list[tuple[str, date]] = []
        for lbl in labels:
            d = _parse_period_label(lbl, kind=kind)
            if d:
                out.append((lbl, d))
        return out

    def _build_financials(
        self, *, symbol: str, period_type: PeriodType, period_end_date: date,
        table_q: dict[str, dict[str, str]], table_a: dict[str, dict[str, str]],
        table_cf: dict[str, dict[str, str]], period_label: str, ratios: dict[str, Any],
    ) -> FinancialsIn:
        src = table_q if period_type == PeriodType.QUARTERLY else table_a

        def col(label: str) -> str | None:
            row = src.get(label) or {}
            return row.get(period_label)

        def col_cf(label: str) -> str | None:
            row = table_cf.get(label) or {}
            return row.get(period_label)

        revenue = normalize_currency_cr(col("Sales") or col("Revenue"))
        net_profit = normalize_currency_cr(col("Net Profit") or col("Net profit"))
        op_profit = normalize_currency_cr(col("Operating Profit"))
        ebitda_margin = normalize_percentage(col("OPM %") or col("Operating Profit Margin"))
        op_cf = normalize_currency_cr(col_cf("Cash from Operating Activity"))

        return FinancialsIn(
            symbol=symbol,
            period_type=period_type,
            period_end_date=period_end_date,
            revenue_cr=_to_cr(revenue),
            ebitda_cr=_to_cr(op_profit),
            ebitda_margin_pct=ebitda_margin,
            net_profit_cr=_to_cr(net_profit),
            eps_ttm=normalize_percentage(ratios.get("eps")),
            pe_ratio=normalize_percentage(ratios.get("stock_p/e")) or normalize_percentage(ratios.get("p/e")),
            pb_ratio=normalize_percentage(ratios.get("price_to_book_value")),
            roe_pct=normalize_percentage(ratios.get("roe")),
            roce_pct=normalize_percentage(ratios.get("roce")),
            debt_equity_ratio=normalize_percentage(ratios.get("debt_to_equity")),
            operating_cf_cr=_to_cr(op_cf),
            free_cf_cr=None,
            book_value=normalize_currency_cr(ratios.get("book_value")),
            raw_payload={"period_label": period_label, "ratios": ratios},
        )

    # ═══════════════════════════════════════════════════════════════
    # Save
    # ═══════════════════════════════════════════════════════════════
    async def save(self, records: list[FinancialsIn]) -> tuple[int, int]:
        if not records:
            return 0, 0
        ins, _ = await self.db.upsert_batch(
            "financials", records,
            conflict_cols=["symbol", "period_type", "period_end_date"],
            jsonb_cols=["raw_payload"],
        )
        return ins, 0


# ─── Helpers ────────────────────────────────────────────────────────
def _to_cr(value: float | None) -> float | None:
    """normalize_currency_cr returns rupees; financials.*_cr is in crores."""
    return None if value is None else round(value / _CR, 4)


_QUARTER_MAP = {
    "Mar": 3, "Jun": 6, "Sep": 9, "Dec": 12,
    "March": 3, "June": 6, "September": 9, "December": 12,
}


def _parse_period_label(label: str, kind: str) -> date | None:
    """Screener labels: 'Mar 2024', 'Jun 2024', 'Mar 2024 ', 'FY24', 'Mar 2023'."""
    s = label.strip()
    if not s:
        return None
    # FY24 / FY 2024
    if s.lower().startswith("fy"):
        try:
            yr = int(s.replace("FY", "").replace("fy", "").strip())
            yr = 2000 + yr if yr < 100 else yr
            return date(yr, 3, 31)
        except ValueError:
            return None
    # 'Mar 2024'
    parts = s.split()
    if len(parts) == 2:
        mon_str, yr_str = parts
        mon = _QUARTER_MAP.get(mon_str)
        if mon and yr_str.isdigit():
            yr = int(yr_str)
            # last day of month: 28/30/31 approximation
            return date(yr, mon, 28)
    return None
