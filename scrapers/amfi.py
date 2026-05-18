"""AMFI India NAV scraper.

Source: https://www.amfiindia.com/spages/NAVAll.txt (pipe-delimited flat file)

Format (real example, abbreviated):
    Scheme Code;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

    Open Ended Schemes(Equity Scheme - Large Cap Fund)
    Aditya Birla Sun Life AMC Limited
    100033;INF209K01157;INF209K01165;Aditya Birla Sun Life Frontline Equity Fund - Growth;567.89;15-May-2026
    ...
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any, ClassVar

import pandas as pd

from core.exceptions import ScraperException
from models.enums import ScraperSource
from models.schemas import MutualFundIn
from scrapers.base import BaseScraper
from services.normalization import normalize_date

NAV_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
HISTORICAL_URL_TMPL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?mf=0&tp=1&frmdt={d}&todt={d}"

# Heuristic split: "Aditya Birla Sun Life Frontline Equity Fund - Growth"
#                  → amc="Aditya Birla Sun Life AMC", scheme="Frontline Equity Fund - Growth"
# We rely on the AMC header line above each block in NAVAll.txt to populate amc/category.
_CATEGORY_HEADER_RE = re.compile(r"^Open Ended Schemes\((.+?)\)$|^Close Ended Schemes\((.+?)\)$|^Interval Fund Schemes\((.+?)\)$")


class AMFIScraper(BaseScraper):
    source: ClassVar[ScraperSource] = ScraperSource.AMFI

    async def fetch(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        text = await self.get_text(NAV_URL, endpoint_label="navall")
        return self._parse_navall(text)

    async def fetch_historical(self, days_back: int = 365) -> list[dict[str, Any]]:
        """Historical ingest: pull the last `days_back` daily files."""
        out: list[dict[str, Any]] = []
        today = datetime.now(tz=timezone.utc).date()
        for i in range(days_back):
            d = today - timedelta(days=i)
            if d.weekday() >= 5:  # NAV not published weekends
                continue
            url = HISTORICAL_URL_TMPL.format(d=d.strftime("%d-%b-%Y"))
            try:
                txt = await self.get_text(url, endpoint_label="navall_historical")
            except ScraperException:
                self.log.warning("historical_nav_skip", date=d.isoformat())
                continue
            out.extend(self._parse_navall(txt))
        return out

    # ─── Parser ─────────────────────────────────────────────────────
    @staticmethod
    def _parse_navall(text: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        current_category: str | None = None
        current_amc: str | None = None

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("Scheme Code"):
                continue  # header

            if ";" not in line:
                # Category or AMC header
                m = _CATEGORY_HEADER_RE.match(line)
                if m:
                    current_category = next((g for g in m.groups() if g), None)
                else:
                    current_amc = line
                continue

            parts = [p.strip() for p in line.split(";")]
            if len(parts) < 6:
                continue
            scheme_code, isin_payout, isin_growth, scheme_name, nav_str, nav_date_str = parts[:6]
            if scheme_code.lower() in ("scheme code", ""):
                continue
            try:
                nav = float(nav_str.replace(",", "")) if nav_str not in ("N.A.", "N/A", "-") else None
            except ValueError:
                nav = None
            if nav is None:
                continue
            out.append({
                "scheme_code": scheme_code,
                "isin_payout": isin_payout or None,
                "isin_growth": isin_growth or None,
                "scheme_name": scheme_name,
                "nav": nav,
                "nav_date_raw": nav_date_str,
                "amc_name": current_amc,
                "category": current_category,
            })
        return out

    # ─── Normalize ──────────────────────────────────────────────────
    async def normalize(self, raw: list[dict[str, Any]]) -> list[MutualFundIn]:
        out: list[MutualFundIn] = []
        for r in raw:
            nav_date = normalize_date(r["nav_date_raw"])
            if nav_date is None:
                continue
            sub_category = self._derive_sub_category(r.get("scheme_name", ""))
            try:
                out.append(MutualFundIn(
                    scheme_code=str(r["scheme_code"]).strip(),
                    isin_payout=r.get("isin_payout"),
                    isin_growth=r.get("isin_growth"),
                    scheme_name=r["scheme_name"],
                    amc_name=r.get("amc_name"),
                    category=r.get("category"),
                    sub_category=sub_category,
                    nav=float(r["nav"]),
                    nav_date=nav_date,
                ))
            except Exception:  # noqa: BLE001
                self.log.warning("amfi_row_skipped", scheme_code=r.get("scheme_code"), exc_info=False)
        return out

    @staticmethod
    def _derive_sub_category(scheme_name: str) -> str | None:
        s = scheme_name.lower()
        if "direct" in s and "growth" in s:
            return "Direct - Growth"
        if "direct" in s and "dividend" in s:
            return "Direct - Dividend"
        if "regular" in s and "growth" in s:
            return "Regular - Growth"
        if "regular" in s and "dividend" in s:
            return "Regular - Dividend"
        if "growth" in s:
            return "Growth"
        if "dividend" in s or "idcw" in s:
            return "IDCW"
        return None

    # ─── Save ───────────────────────────────────────────────────────
    async def save(self, records: list[MutualFundIn]) -> tuple[int, int]:
        if not records:
            return 0, 0
        # Bulk UPSERT — NAVAll can be 15k+ rows
        BATCH = 1000
        total = 0
        for i in range(0, len(records), BATCH):
            chunk = records[i : i + BATCH]
            ins, _ = await self.db.upsert_batch(
                table="mutual_funds",
                rows=chunk,
                conflict_cols=["scheme_code", "nav_date"],
            )
            total += ins
        return total, 0
