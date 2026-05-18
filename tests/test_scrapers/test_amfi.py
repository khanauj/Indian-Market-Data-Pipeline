from __future__ import annotations

from datetime import date

import pytest

from scrapers.amfi import AMFIScraper


SAMPLE_NAVALL = """\
Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

Open Ended Schemes(Equity Scheme - Large Cap Fund)

Aditya Birla Sun Life Mutual Fund

100033;INF209K01157;INF209K01165;Aditya Birla Sun Life Frontline Equity Fund - Growth;567.89;15-May-2026
100034;INF209K01173;INF209K01181;Aditya Birla Sun Life Frontline Equity Fund - IDCW;234.56;15-May-2026

Open Ended Schemes(Debt Scheme - Liquid Fund)

HDFC Mutual Fund

200001;INF179K01ABC;INF179K01XYZ;HDFC Liquid Fund - Direct Plan - Growth;3456.78;15-May-2026
200002;-;INF179K01DEF;HDFC Liquid Fund - Regular Plan - Growth;N.A.;15-May-2026
"""


class TestAMFIParser:
    def test_parses_rows_skipping_invalid_nav(self):
        rows = AMFIScraper._parse_navall(SAMPLE_NAVALL)
        # 3 valid rows; the N.A. row is dropped
        codes = [r["scheme_code"] for r in rows]
        assert codes == ["100033", "100034", "200001"]
        assert rows[0]["amc_name"] == "Aditya Birla Sun Life Mutual Fund"
        assert rows[0]["category"] == "Equity Scheme - Large Cap Fund"
        assert rows[2]["amc_name"] == "HDFC Mutual Fund"
        assert rows[2]["category"] == "Debt Scheme - Liquid Fund"

    def test_parses_navs_and_dates(self):
        rows = AMFIScraper._parse_navall(SAMPLE_NAVALL)
        assert rows[0]["nav"] == 567.89
        assert rows[0]["nav_date_raw"] == "15-May-2026"


class TestAMFISubCategory:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Frontline Equity Fund - Direct - Growth", "Direct - Growth"),
            ("Frontline Equity Fund - Regular Plan - Growth", "Regular - Growth"),
            ("HDFC Liquid Fund - Growth", "Growth"),
            ("HDFC Liquid Fund - IDCW", "IDCW"),
            ("Random Plan", None),
        ],
    )
    def test_categorize(self, name, expected):
        assert AMFIScraper._derive_sub_category(name) == expected


@pytest.mark.asyncio
class TestAMFINormalize:
    async def test_normalize_emits_pydantic(self, fake_db):
        s = AMFIScraper(fake_db)
        raw = AMFIScraper._parse_navall(SAMPLE_NAVALL)
        models = await s.normalize(raw)
        assert len(models) == 3
        m = models[0]
        assert m.scheme_code == "100033"
        assert m.nav == 567.89
        assert m.nav_date == date(2026, 5, 15)
        assert m.amc_name == "Aditya Birla Sun Life Mutual Fund"

    async def test_save_batches_upsert(self, fake_db):
        s = AMFIScraper(fake_db)
        models = await s.normalize(AMFIScraper._parse_navall(SAMPLE_NAVALL))
        inserted, skipped = await s.save(models)
        assert inserted == 3
        assert skipped == 0
        assert fake_db.upserts[0]["table"] == "mutual_funds"
        assert fake_db.upserts[0]["conflict_cols"] == ["scheme_code", "nav_date"]
