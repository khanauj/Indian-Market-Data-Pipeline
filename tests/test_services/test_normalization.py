from __future__ import annotations

from datetime import date

import pytest

from services.normalization import (
    normalize_currency_cr,
    normalize_date,
    normalize_null,
    normalize_percentage,
    normalize_sector,
    normalize_symbol,
    normalize_volume,
)


class TestNormalizeCurrency:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("₹1,234.56 Cr", 12_345_600_000.0),
            ("1,234.56 Cr", 12_345_600_000.0),
            ("₹12.5 L", 1_250_000.0),
            ("Rs. 100", 100.0),
            ("1234", 1234.0),
            (1234.56, 1234.56),
            ("-", None),
            ("", None),
            (None, None),
        ],
    )
    def test_parses_known_shapes(self, raw, expected):
        assert normalize_currency_cr(raw) == expected

    def test_handles_negative(self):
        assert normalize_currency_cr("-12.5 Cr") == -125_000_000.0


class TestNormalizePercentage:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("12.34%", 12.34),
            ("12.34", 12.34),
            ("--", None),
            (None, None),
            (12.5, 12.5),
            ("1,234.5%", 1234.5),
        ],
    )
    def test_pct(self, raw, expected):
        assert normalize_percentage(raw) == expected


class TestNormalizeVolume:
    def test_lakh(self):
        assert normalize_volume("12.5L") == 1_250_000

    def test_crore(self):
        assert normalize_volume("3.2Cr") == 32_000_000

    def test_with_commas(self):
        assert normalize_volume("1,23,456") == 123_456

    def test_null(self):
        assert normalize_volume("N/A") is None


class TestNormalizeSymbol:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("RELIANCE", "RELIANCE"),
            ("reliance", "RELIANCE"),
            ("RELIANCE.NS", "RELIANCE"),
            ("RELIANCE.BO", "RELIANCE"),
            ("  TCS  ", "TCS"),
            ("HDFC-BK", "HDFC-BK"),
            ("LOWER_invalid_token@@", None),
            ("", None),
            (None, None),
        ],
    )
    def test_symbol(self, raw, expected):
        assert normalize_symbol(raw) == expected


class TestNormalizeDate:
    def test_ddmmyyyy(self):
        assert normalize_date("15/05/2026") == date(2026, 5, 15)

    def test_dd_mon_yyyy(self):
        assert normalize_date("15-May-2026") == date(2026, 5, 15)

    def test_iso(self):
        assert normalize_date("2026-05-15") == date(2026, 5, 15)

    def test_garbage(self):
        assert normalize_date("not a date") is None

    def test_epoch_seconds(self):
        # 2026-05-15 00:00 UTC = 1_778_976_000
        assert normalize_date(1_778_976_000) == date(2026, 5, 15)


class TestNormalizeNull:
    @pytest.mark.parametrize("raw", ["-", "--", "N/A", "n/a", "", "null", None])
    def test_null_tokens(self, raw):
        assert normalize_null(raw) is None

    def test_pass_through_value(self):
        assert normalize_null("hello") == "hello"
        assert normalize_null(42) == 42


class TestNormalizeSector:
    def test_canonical_mapping(self):
        assert normalize_sector("FINANCIAL SERVICES") == "Financial Services"
        assert normalize_sector("BANKS") == "Banking"

    def test_unknown_titlecase(self):
        assert normalize_sector("widgets and gizmos") == "Widgets And Gizmos"

    def test_null(self):
        assert normalize_sector(None) is None
