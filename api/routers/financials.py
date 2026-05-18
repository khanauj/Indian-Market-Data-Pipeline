from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from api.dependencies import db_dep
from models.enums import PeriodType
from models.schemas import FinancialsOut
from services.storage import Storage

router = APIRouter(prefix="/financials", tags=["financials"])


@router.get("/{symbol}", response_model=list[FinancialsOut])
async def get_financials(
    symbol: str,
    response: Response,
    period_type: PeriodType | None = None,
    limit: int = Query(20, ge=1, le=200),
    db: Storage = Depends(db_dep),
) -> list[FinancialsOut]:
    symbol = symbol.upper()
    args: list[object] = [symbol]
    where = "symbol = $1"
    if period_type is not None:
        args.append(period_type.value)
        where += f" AND period_type = ${len(args)}"
    args.append(limit)
    sql = f"""SELECT * FROM financials
              WHERE {where}
              ORDER BY period_end_date DESC, scraped_at DESC
              LIMIT ${len(args)}"""
    rows = await db.fetch(sql, *args)
    response.headers["Cache-Control"] = "public, max-age=300"
    return [FinancialsOut.model_validate(dict(r)) for r in rows]
