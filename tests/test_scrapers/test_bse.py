from __future__ import annotations

from datetime import datetime

import pytest

from models.enums import FilingType
from models.schemas import StockMasterIn
from scrapers.bse import BSEScraper, _categorize_filing


class TestFilingCategorization:
    @pytest.mark.parametrize(
        ("category", "expected"),
        [
            ("Board Meeting Outcome", FilingType.BOARD_MEETING),
            ("Dividend Distribution", FilingType.DIVIDEND),
            ("Stock Split", FilingType.SPLIT),
            ("Share Buyback Announcement", FilingType.BUYBACK),
            ("Annual Report", FilingType.ANNUAL_REPORT),
            ("Quarterly Results", FilingType.RESULTS),
            ("Shareholding Pattern", FilingType.SHAREHOLDING),
            ("Some general announcement", FilingType.ANNOUNCEMENT),
            ("Mystery box", FilingType.OTHER),
        ],
    )
    def test_categorizes(self, category, expected):
        assert _categorize_filing(category) == expected


@pytest.mark.asyncio
class TestBSEMasterNormalize:
    async def test_dedupes_on_isin(self, fake_db):
        s = BSEScraper(fake_db)
        raw = [
            {
                "_kind": "master", "symbol": "RELIANCE", "isin": "INE002A01018",
                "company_name": "Reliance Industries Ltd", "industry": "Oil & Gas",
                "sector": "Energy", "raw": {},
            },
            {
                "_kind": "master", "symbol": "RELIANCE-2", "isin": "INE002A01018",
                "company_name": "Reliance dup", "industry": "Oil & Gas",
                "sector": "Energy", "raw": {},
            },
            {
                "_kind": "master", "symbol": "TCS", "isin": "INE467B01029",
                "company_name": "Tata Consultancy Services", "industry": "IT",
                "sector": "IT", "raw": {},
            },
        ]
        models = await s._normalize_master(raw)
        symbols = [m.symbol for m in models]
        assert "RELIANCE" in symbols
        assert "TCS" in symbols
        # Duplicate ISIN dropped
        assert len([m for m in models if m.isin == "INE002A01018"]) == 1
        assert all(isinstance(m, StockMasterIn) for m in models)
