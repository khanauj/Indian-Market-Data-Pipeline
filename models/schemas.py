from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from models.enums import (
    Exchange,
    FilingType,
    MoverType,
    PeriodType,
    ScraperSource,
    ScraperStatus,
)

# ════════════════════════════════════════════════════════════════════
# Base
# ════════════════════════════════════════════════════════════════════
class _ORMModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=False,
        extra="ignore",
    )


# ════════════════════════════════════════════════════════════════════
# Stocks master
# ════════════════════════════════════════════════════════════════════
class StockMasterIn(_ORMModel):
    symbol: str = Field(min_length=1, max_length=32)
    isin: str | None = Field(default=None, min_length=12, max_length=12)
    company_name: str
    exchange: Exchange
    sector: str | None = None
    industry: str | None = None
    market_cap_cr: float | None = None
    listing_date: date | None = None
    is_active: bool = True
    raw_payload: dict[str, Any] | None = None

    @field_validator("symbol")
    @classmethod
    def _upper_symbol(cls, v: str) -> str:
        return v.upper().strip()


class StockMasterOut(StockMasterIn):
    id: int
    created_at: datetime
    updated_at: datetime


# ════════════════════════════════════════════════════════════════════
# Stock prices
# ════════════════════════════════════════════════════════════════════
class StockPriceIn(_ORMModel):
    symbol: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    ltp: float | None = None
    volume: int | None = None
    delivery_qty: int | None = None
    delivery_pct: float | None = None
    total_buy_qty: int | None = None
    total_sell_qty: int | None = None
    timestamp: datetime


class StockPriceOut(StockPriceIn):
    id: int


# ════════════════════════════════════════════════════════════════════
# Financials
# ════════════════════════════════════════════════════════════════════
class FinancialsIn(_ORMModel):
    symbol: str
    period_type: PeriodType
    period_end_date: date
    revenue_cr: float | None = None
    ebitda_cr: float | None = None
    ebitda_margin_pct: float | None = None
    net_profit_cr: float | None = None
    eps_ttm: float | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    roe_pct: float | None = None
    roce_pct: float | None = None
    debt_equity_ratio: float | None = None
    operating_cf_cr: float | None = None
    free_cf_cr: float | None = None
    book_value: float | None = None
    raw_payload: dict[str, Any] | None = None


class FinancialsOut(FinancialsIn):
    id: int
    scraped_at: datetime


# ════════════════════════════════════════════════════════════════════
# Mutual funds
# ════════════════════════════════════════════════════════════════════
class MutualFundIn(_ORMModel):
    scheme_code: str
    isin_payout: str | None = None
    isin_growth: str | None = None
    scheme_name: str
    amc_name: str | None = None
    category: str | None = None
    sub_category: str | None = None
    nav: float
    nav_date: date


class MutualFundOut(MutualFundIn):
    id: int


# ════════════════════════════════════════════════════════════════════
# Filings
# ════════════════════════════════════════════════════════════════════
class CompanyFilingIn(_ORMModel):
    symbol: str
    filing_type: FilingType
    title: str
    document_url: HttpUrl | None = None
    filing_date: datetime
    bse_scrip_code: str | None = None
    exchange: Exchange
    raw_payload: dict[str, Any] | None = None


class CompanyFilingOut(CompanyFilingIn):
    id: int


# ════════════════════════════════════════════════════════════════════
# News
# ════════════════════════════════════════════════════════════════════
class CompanyNewsIn(_ORMModel):
    symbol: str
    headline: str
    url_hash: str = Field(min_length=64, max_length=64)
    full_url: HttpUrl
    source: str
    summary: str | None = None
    sentiment: float | None = None
    published_at: datetime
    scraped_at: datetime


class CompanyNewsOut(CompanyNewsIn):
    id: int


# ════════════════════════════════════════════════════════════════════
# Top gainers / losers
# ════════════════════════════════════════════════════════════════════
class TopMoverIn(_ORMModel):
    symbol: str
    type: MoverType
    ltp: float
    change_pct: float
    volume: int | None = None
    timestamp: datetime


class TopMoverOut(TopMoverIn):
    id: int


# ════════════════════════════════════════════════════════════════════
# Indices
# ════════════════════════════════════════════════════════════════════
class MarketIndexIn(_ORMModel):
    index_name: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    change_pct: float | None = None
    advances: int | None = None
    declines: int | None = None
    timestamp: datetime


class MarketIndexOut(MarketIndexIn):
    id: int


# ════════════════════════════════════════════════════════════════════
# Operational
# ════════════════════════════════════════════════════════════════════
class ScraperRunLog(_ORMModel):
    source: ScraperSource
    status: ScraperStatus
    records_inserted: int = 0
    records_skipped: int = 0
    error_msg: str | None = None
    started_at: datetime
    ended_at: datetime | None = None


class SymbolSlugMap(_ORMModel):
    nse_symbol: str
    bse_code: str | None = None
    screener_slug: str | None = None
    mc_slug: str | None = None


class ScraperCheckpoint(_ORMModel):
    source: ScraperSource
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    cursor_value: str | None = None


# ════════════════════════════════════════════════════════════════════
# API envelope responses
# ════════════════════════════════════════════════════════════════════
class HealthResponse(BaseModel):
    status: str
    version: str
    env: str
    checks: dict[str, dict[str, Any]]


class PaginatedResponse(BaseModel):
    items: list[Any]
    next_cursor: str | None = None
    total: int | None = None


class StockProfileResponse(BaseModel):
    master: StockMasterOut
    latest_price: StockPriceOut | None
    ratios: FinancialsOut | None
