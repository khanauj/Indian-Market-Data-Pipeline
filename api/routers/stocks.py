from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from api.dependencies import db_dep
from models.schemas import (
    FinancialsOut,
    PaginatedResponse,
    StockMasterOut,
    StockPriceOut,
    StockProfileResponse,
)
from services.storage import Storage

router = APIRouter(prefix="", tags=["stocks"])

_CACHE_HEADERS_LATEST = {"Cache-Control": "public, max-age=30"}
_CACHE_HEADERS_STATIC = {"Cache-Control": "public, max-age=3600"}


@router.get("/stocks", response_model=PaginatedResponse)
async def list_stocks(
    response: Response,
    sector: str | None = None,
    exchange: str | None = None,
    cursor: int = 0,
    limit: int = Query(50, ge=1, le=500),
    db: Storage = Depends(db_dep),
) -> PaginatedResponse:
    where = ["is_active = TRUE"]
    args: list[Any] = []
    if sector:
        args.append(sector)
        where.append(f"sector = ${len(args)}")
    if exchange:
        args.append(exchange.upper())
        where.append(f"exchange = ${len(args)}")
    args.append(cursor)
    args.append(limit)
    sql = f"""
        SELECT id, symbol, isin, company_name, exchange, sector, industry,
               market_cap_cr, listing_date, is_active, raw_payload,
               created_at, updated_at
        FROM stocks_master
        WHERE {" AND ".join(where)} AND id > ${len(args) - 1}
        ORDER BY id
        LIMIT ${len(args)}
    """
    rows = await db.fetch(sql, *args)
    items = [StockMasterOut.model_validate(dict(r)) for r in rows]
    next_cursor = str(rows[-1]["id"]) if len(rows) == limit else None
    response.headers.update(_CACHE_HEADERS_STATIC)
    return PaginatedResponse(items=items, next_cursor=next_cursor)


@router.get("/stock/{symbol}", response_model=StockProfileResponse)
async def stock_profile(
    symbol: str,
    response: Response,
    db: Storage = Depends(db_dep),
) -> StockProfileResponse:
    symbol = symbol.upper()
    master_row = await db.fetchrow(
        "SELECT * FROM stocks_master WHERE symbol = $1 ORDER BY id LIMIT 1", symbol
    )
    if master_row is None:
        raise HTTPException(404, detail=f"stock {symbol} not found")
    price_row = await db.fetchrow(
        "SELECT * FROM stock_prices WHERE symbol = $1 ORDER BY timestamp DESC LIMIT 1", symbol
    )
    fin_row = await db.fetchrow(
        """SELECT * FROM financials
           WHERE symbol = $1 ORDER BY period_end_date DESC, scraped_at DESC LIMIT 1""",
        symbol,
    )
    response.headers.update(_CACHE_HEADERS_LATEST)
    return StockProfileResponse(
        master=StockMasterOut.model_validate(dict(master_row)),
        latest_price=StockPriceOut.model_validate(dict(price_row)) if price_row else None,
        ratios=FinancialsOut.model_validate(dict(fin_row)) if fin_row else None,
    )


@router.get("/stock/{symbol}/prices", response_model=list[StockPriceOut])
async def stock_prices(
    symbol: str,
    response: Response,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(500, ge=1, le=5000),
    db: Storage = Depends(db_dep),
) -> list[StockPriceOut]:
    symbol = symbol.upper()
    start_ts = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc) if start \
        else datetime.now(tz=timezone.utc) - timedelta(days=30)
    end_ts = datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc) if end \
        else datetime.now(tz=timezone.utc)
    rows = await db.fetch(
        """SELECT * FROM stock_prices
           WHERE symbol = $1 AND timestamp BETWEEN $2 AND $3
           ORDER BY timestamp DESC LIMIT $4""",
        symbol, start_ts, end_ts, limit,
    )
    response.headers.update(_CACHE_HEADERS_LATEST)
    return [StockPriceOut.model_validate(dict(r)) for r in rows]
