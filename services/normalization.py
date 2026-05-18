"""Field-level normalization helpers.

Pure functions, no I/O, no async. Each maps messy upstream values to
typed Python primitives, returning None when input clearly means "missing".
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

from dateutil import parser as dateparser

from core.exceptions import NormalizationException

_NULL_TOKENS = {"", "-", "--", "n/a", "na", "nan", "null", "none"}
_CR = 1e7      # 1 crore  = 10,000,000
_LAKH = 1e5    # 1 lakh   = 100,000

_NUM_PATTERN = re.compile(r"[-+]?\d*\.?\d+")
_CR_PATTERN = re.compile(r"(?i)\bcr(ore)?s?\b")
_LAKH_PATTERN = re.compile(r"(?i)\b(l|lakh|lac|lacs)\b")


# ─── Null safety ────────────────────────────────────────────────────
def normalize_null(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in _NULL_TOKENS:
        return None
    return value


# ─── Currency (₹ x Cr / x L) ────────────────────────────────────────
def normalize_currency_cr(value: Any) -> float | None:
    """Parse Indian-formatted currency into a float in *rupees*.

    Examples
    --------
    "₹1,234.56 Cr" → 12_345_600_000.0
    "₹12.5 L"      → 1_250_000.0
    "1234.56"      → 1234.56
    "-" / None     → None
    """
    cleaned = normalize_null(value)
    if cleaned is None:
        return None
    if isinstance(cleaned, (int, float)):
        return float(cleaned)
    if not isinstance(cleaned, str):
        raise NormalizationException("unsupported currency type", value=value, type=type(value).__name__)

    s = cleaned.replace("₹", "").replace(",", "").replace("Rs.", "").replace("Rs", "").strip()
    if not s:
        return None

    has_cr = bool(_CR_PATTERN.search(s))
    has_lakh = bool(_LAKH_PATTERN.search(s)) and not has_cr  # Cr wins ties
    m = _NUM_PATTERN.search(s)
    if not m:
        return None
    n = float(m.group())
    if has_cr:
        return n * _CR
    if has_lakh:
        return n * _LAKH
    return n


# ─── Percentage ─────────────────────────────────────────────────────
def normalize_percentage(value: Any) -> float | None:
    """'12.34%' → 12.34 ; '12.34' → 12.34 ; '-' → None."""
    cleaned = normalize_null(value)
    if cleaned is None:
        return None
    if isinstance(cleaned, (int, float)):
        return float(cleaned)
    if not isinstance(cleaned, str):
        return None
    s = cleaned.replace("%", "").replace(",", "").strip()
    m = _NUM_PATTERN.search(s)
    return float(m.group()) if m else None


# ─── Volume ─────────────────────────────────────────────────────────
def normalize_volume(value: Any) -> int | None:
    """'12.5L' → 1_250_000, '3.2Cr' → 32_000_000, '1,23,456' → 123456."""
    cleaned = normalize_null(value)
    if cleaned is None:
        return None
    if isinstance(cleaned, (int, float)):
        return int(cleaned)
    if not isinstance(cleaned, str):
        return None
    s = cleaned.replace(",", "").strip()
    if not s:
        return None
    has_cr = bool(_CR_PATTERN.search(s)) or s.lower().endswith("cr")
    has_lakh = (not has_cr) and (bool(_LAKH_PATTERN.search(s)) or s.lower().endswith("l"))
    m = _NUM_PATTERN.search(s)
    if not m:
        return None
    n = float(m.group())
    if has_cr:
        n *= _CR
    elif has_lakh:
        n *= _LAKH
    return int(round(n))


# ─── Symbol ─────────────────────────────────────────────────────────
_SYMBOL_RE = re.compile(r"^[A-Z0-9&.\-]{1,32}$")


def normalize_symbol(value: Any) -> str | None:
    """Strip .NS/.BO suffix, uppercase, validate shape. Returns None if invalid."""
    cleaned = normalize_null(value)
    if cleaned is None or not isinstance(cleaned, str):
        return None
    s = cleaned.strip().upper()
    for suffix in (".NS", ".BO", ".NSE", ".BSE"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    return s if _SYMBOL_RE.match(s) else None


# ─── Date ───────────────────────────────────────────────────────────
def normalize_date(value: Any) -> date | None:
    """Accept DD-Mon-YYYY, DD/MM/YYYY, ISO, unix epoch — return a date or None."""
    cleaned = normalize_null(value)
    if cleaned is None:
        return None
    if isinstance(cleaned, date) and not isinstance(cleaned, datetime):
        return cleaned
    if isinstance(cleaned, datetime):
        return cleaned.date()
    if isinstance(cleaned, (int, float)):
        # Heuristic: ms vs s
        epoch = cleaned / 1000 if cleaned > 1e11 else cleaned
        return datetime.fromtimestamp(epoch, tz=timezone.utc).date()
    if not isinstance(cleaned, str):
        return None
    s = cleaned.strip()
    if not s:
        return None
    try:
        # dayfirst=True handles DD/MM/YYYY common in Indian sources
        return dateparser.parse(s, dayfirst=True).date()
    except (ValueError, OverflowError, dateparser.ParserError):
        return None


# ─── Datetime (timezone-aware) ──────────────────────────────────────
def normalize_datetime(value: Any) -> datetime | None:
    cleaned = normalize_null(value)
    if cleaned is None:
        return None
    if isinstance(cleaned, datetime):
        return cleaned if cleaned.tzinfo else cleaned.replace(tzinfo=timezone.utc)
    if isinstance(cleaned, (int, float)):
        epoch = cleaned / 1000 if cleaned > 1e11 else cleaned
        return datetime.fromtimestamp(epoch, tz=timezone.utc)
    if not isinstance(cleaned, str):
        return None
    try:
        dt = dateparser.parse(cleaned.strip(), dayfirst=True)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError, dateparser.ParserError):
        return None


# ─── Sector canonical mapping ───────────────────────────────────────
_SECTOR_MAP: dict[str, str] = {
    "FINANCIAL SERVICES": "Financial Services",
    "FIN SERV": "Financial Services",
    "BANKS": "Banking",
    "PRIVATE BANKS": "Banking",
    "PUBLIC SECTOR BANKS": "Banking",
    "IT": "Information Technology",
    "SOFTWARE & SERVICES": "Information Technology",
    "PHARMA": "Pharmaceuticals",
    "PHARMA & HEALTHCARE": "Pharmaceuticals",
    "FMCG": "Consumer Goods",
    "CONSUMER DURABLES": "Consumer Durables",
    "AUTOMOBILE": "Automobile",
    "AUTO ANCILLARIES": "Auto Ancillaries",
    "OIL & GAS": "Energy",
    "POWER": "Energy",
    "METALS": "Metals & Mining",
    "METALS & MINING": "Metals & Mining",
    "REALTY": "Real Estate",
    "TELECOM": "Telecommunications",
}


def normalize_sector(value: Any) -> str | None:
    cleaned = normalize_null(value)
    if cleaned is None or not isinstance(cleaned, str):
        return None
    key = cleaned.strip().upper()
    return _SECTOR_MAP.get(key, cleaned.strip().title())
