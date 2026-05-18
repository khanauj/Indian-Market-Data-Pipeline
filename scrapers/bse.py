"""BSE India scraper — company master + corporate announcements.

BSE's public APIs use Origin/Referer checks but no captcha. We paginate
the company master, then fan-out announcement fetches under a semaphore.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar

from core.config import settings
from models.enums import Exchange, FilingType, ScraperSource
from models.schemas import CompanyFilingIn, StockMasterIn
from scrapers.base import BaseScraper
from services.normalization import normalize_date, normalize_datetime, normalize_symbol

BSE_BASE = "https://api.bseindia.com/BseIndiaAPI/api"
LIST_OF_SCRIP = f"{BSE_BASE}/ListofScripData/w"
ANNOUNCEMENTS = f"{BSE_BASE}/AnnGetAnnouncementXml/w"
CORP_ACTION = f"{BSE_BASE}/CorporateAction/w"


class BSEScraper(BaseScraper):
    source: ClassVar[ScraperSource] = ScraperSource.BSE

    def _default_headers(self) -> dict[str, str]:
        h = super()._default_headers()
        h.update({
            "Referer": "https://www.bseindia.com/",
            "Origin": "https://www.bseindia.com",
        })
        return h

    # ═══════════════════════════════════════════════════════════════
    # Dispatcher
    # ═══════════════════════════════════════════════════════════════
    async def fetch(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        task = (args[0] if args else kwargs.get("task")) or "filings"
        if task == "master":
            return await self._fetch_master()
        if task == "filings":
            return await self._fetch_recent_filings()
        raise ValueError(f"unknown BSE task: {task}")

    # ─── Company master ─────────────────────────────────────────────
    async def _fetch_master(self) -> list[dict[str, Any]]:
        """Paginate the BSE listed-securities master.

        Endpoint expects ?Industry=&segment=Equity&status=Active.
        We accept the entire page (no real pagination on this endpoint —
        it returns the full list).
        """
        params = {
            "Group": "", "Scripcode": "", "industry": "",
            "segment": "Equity", "status": "Active",
        }
        data = await self.get_json(LIST_OF_SCRIP, params=params, endpoint_label="list_of_scrip")
        rows = data if isinstance(data, list) else data.get("Table", [])
        return [
            {
                "_kind": "master",
                "symbol": (r.get("scrip_id") or r.get("ScripID") or r.get("SC_ID") or "").strip(),
                "bse_code": str(r.get("SCRIP_CD") or r.get("Scripcode") or "").strip(),
                "isin": (r.get("ISIN_NUMBER") or r.get("ISIN") or "").strip() or None,
                "company_name": (r.get("scrip_name") or r.get("Scripname") or "").strip(),
                "industry": (r.get("INDUSTRY") or r.get("Industry") or "").strip() or None,
                "sector": (r.get("SECTOR_NAME") or r.get("Sector") or "").strip() or None,
                "raw": r,
            }
            for r in rows
            if (r.get("scrip_id") or r.get("ScripID") or r.get("SC_ID"))
        ]

    # ─── Filings / announcements ────────────────────────────────────
    async def _fetch_recent_filings(self) -> list[dict[str, Any]]:
        """Last 24h of corporate announcements across all symbols.

        BSE's announcement endpoint accepts a date range (DD/MM/YYYY).
        Returns top-level entries with PDF links.
        """
        today = datetime.now(tz=timezone.utc).date()
        yesterday = today - timedelta(days=1)
        params = {
            "pageno": 1,
            "strCat": "-1",
            "strPrevDate": yesterday.strftime("%Y%m%d"),
            "strScrip": "",
            "strSearch": "P",
            "strToDate": today.strftime("%Y%m%d"),
            "strType": "C",
        }
        data = await self.get_json(ANNOUNCEMENTS, params=params, endpoint_label="announcements")
        rows = data.get("Table", []) if isinstance(data, dict) else []
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append({
                "_kind": "filing",
                "symbol": (r.get("SCRIP_CD") or r.get("scrip_id") or "").strip(),
                "headline": (r.get("HEADLINE") or r.get("NEWSSUB") or "").strip(),
                "category": (r.get("CATEGORYNAME") or r.get("NEWS_SUBJECT") or "").strip(),
                "filing_date_raw": r.get("NEWS_DT") or r.get("DT_TM"),
                "doc_url": r.get("ATTACHMENTNAME"),
                "bse_scrip_code": str(r.get("SCRIP_CD") or "").strip(),
                "raw": r,
            })
        return out

    # ═══════════════════════════════════════════════════════════════
    # Normalize
    # ═══════════════════════════════════════════════════════════════
    async def normalize(self, raw: list[dict[str, Any]]) -> list[Any]:
        if not raw:
            return []
        kind = raw[0].get("_kind")
        if kind == "master":
            return await self._normalize_master(raw)
        if kind == "filing":
            return await self._normalize_filings(raw)
        return []

    async def _normalize_master(self, raw: list[dict[str, Any]]) -> list[StockMasterIn]:
        out: list[StockMasterIn] = []
        seen_isin: set[str] = set()
        for r in raw:
            sym = normalize_symbol(r.get("symbol"))
            if not sym:
                continue
            isin = r.get("isin")
            if isin and isin in seen_isin:
                continue
            if isin:
                seen_isin.add(isin)
            try:
                out.append(StockMasterIn(
                    symbol=sym,
                    isin=isin,
                    company_name=r["company_name"],
                    exchange=Exchange.BSE,
                    sector=r.get("sector"),
                    industry=r.get("industry"),
                    is_active=True,
                    raw_payload=r.get("raw"),
                ))
            except Exception:  # noqa: BLE001
                self.log.warning("bse_master_skip", symbol=sym, exc_info=False)
        return out

    async def _normalize_filings(self, raw: list[dict[str, Any]]) -> list[CompanyFilingIn]:
        out: list[CompanyFilingIn] = []
        sem = asyncio.Semaphore(settings.scraper_concurrency)

        async def _one(r: dict[str, Any]) -> CompanyFilingIn | None:
            async with sem:
                filing_dt = normalize_datetime(r.get("filing_date_raw")) or datetime.now(tz=timezone.utc)
                doc_url = r.get("doc_url")
                if doc_url and not str(doc_url).startswith("http"):
                    doc_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{doc_url}"
                ftype = _categorize_filing(r.get("category", ""))
                try:
                    return CompanyFilingIn(
                        symbol=str(r.get("symbol") or r.get("bse_scrip_code") or ""),
                        filing_type=ftype,
                        title=r.get("headline") or "(no headline)",
                        document_url=doc_url or None,
                        filing_date=filing_dt,
                        bse_scrip_code=r.get("bse_scrip_code"),
                        exchange=Exchange.BSE,
                        raw_payload=r.get("raw"),
                    )
                except Exception:  # noqa: BLE001
                    self.log.warning("bse_filing_skip", scrip=r.get("bse_scrip_code"), exc_info=False)
                    return None

        results = await asyncio.gather(*(_one(r) for r in raw))
        return [x for x in results if x is not None]

    # ═══════════════════════════════════════════════════════════════
    # Save
    # ═══════════════════════════════════════════════════════════════
    async def save(self, records: list[Any]) -> tuple[int, int]:
        if not records:
            return 0, 0
        if isinstance(records[0], StockMasterIn):
            ins, _ = await self.db.upsert_batch(
                "stocks_master", records,
                conflict_cols=["symbol", "exchange"],
                jsonb_cols=["raw_payload"],
            )
            return ins, 0
        if isinstance(records[0], CompanyFilingIn):
            ins, _ = await self.db.upsert_batch(
                "company_filings", records,
                conflict_cols=["symbol", "title", "filing_date"],
                jsonb_cols=["raw_payload"],
            )
            return ins, 0
        return 0, 0


# ─── Categorization ─────────────────────────────────────────────────
_CATEGORY_MAP: dict[str, FilingType] = {
    "board meeting": FilingType.BOARD_MEETING,
    "dividend": FilingType.DIVIDEND,
    "bonus": FilingType.BONUS,
    "split": FilingType.SPLIT,
    "rights": FilingType.RIGHTS,
    "buyback": FilingType.BUYBACK,
    "shareholding": FilingType.SHAREHOLDING,
    "result": FilingType.RESULTS,
    "annual report": FilingType.ANNUAL_REPORT,
    "corporate action": FilingType.CORPORATE_ACTION,
}


def _categorize_filing(category: str) -> FilingType:
    c = (category or "").lower()
    for token, ftype in _CATEGORY_MAP.items():
        if token in c:
            return ftype
    if "announcement" in c:
        return FilingType.ANNOUNCEMENT
    return FilingType.OTHER
