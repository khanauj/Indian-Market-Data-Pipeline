from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from api.dependencies import db_dep
from models.schemas import CompanyNewsOut
from services.storage import Storage

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/{symbol}", response_model=list[CompanyNewsOut])
async def get_news(
    symbol: str,
    response: Response,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    min_sentiment: float | None = None,
    max_sentiment: float | None = None,
    db: Storage = Depends(db_dep),
) -> list[CompanyNewsOut]:
    symbol = symbol.upper()
    args: list[object] = [symbol]
    where = "symbol = $1"
    if min_sentiment is not None:
        args.append(min_sentiment)
        where += f" AND sentiment >= ${len(args)}"
    if max_sentiment is not None:
        args.append(max_sentiment)
        where += f" AND sentiment <= ${len(args)}"
    args.extend([limit, offset])
    sql = f"""SELECT * FROM company_news
              WHERE {where}
              ORDER BY published_at DESC
              LIMIT ${len(args) - 1} OFFSET ${len(args)}"""
    rows = await db.fetch(sql, *args)
    response.headers["Cache-Control"] = "public, max-age=60"
    return [CompanyNewsOut.model_validate(dict(r)) for r in rows]
