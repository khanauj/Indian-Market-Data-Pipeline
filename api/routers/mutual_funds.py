from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Response

from api.dependencies import db_dep
from models.schemas import MutualFundOut, PaginatedResponse
from services.storage import Storage

router = APIRouter(prefix="/mutual-funds", tags=["mutual_funds"])


@router.get("", response_model=PaginatedResponse)
async def list_mutual_funds(
    response: Response,
    amc: str | None = None,
    category: str | None = None,
    cursor: int = 0,
    limit: int = Query(100, ge=1, le=1000),
    db: Storage = Depends(db_dep),
) -> PaginatedResponse:
    args: list[object] = [cursor]
    where = "id > $1"
    if amc:
        args.append(amc)
        where += f" AND amc_name ILIKE ${len(args)}"
    if category:
        args.append(category)
        where += f" AND category = ${len(args)}"
    args.append(limit)
    sql = f"""
        SELECT * FROM (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY scheme_code ORDER BY nav_date DESC, id) AS rn
            FROM mutual_funds
            WHERE {where}
        ) WHERE rn = 1
        ORDER BY id
        LIMIT ${len(args)}
    """
    rows = await db.fetch(sql, *args)
    items = [MutualFundOut.model_validate({k: v for k, v in dict(r).items() if k != "rn"}) for r in rows]
    next_cursor = str(rows[-1]["id"]) if len(rows) == limit else None
    response.headers["Cache-Control"] = "public, max-age=600"
    return PaginatedResponse(items=items, next_cursor=next_cursor)


@router.get("/{code}/nav", response_model=list[MutualFundOut])
async def get_nav_history(
    code: str,
    response: Response,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(365, ge=1, le=3650),
    db: Storage = Depends(db_dep),
) -> list[MutualFundOut]:
    start = start or date.today() - timedelta(days=365)
    end = end or date.today()
    rows = await db.fetch(
        """SELECT * FROM mutual_funds
           WHERE scheme_code = $1 AND nav_date BETWEEN $2 AND $3
           ORDER BY nav_date DESC LIMIT $4""",
        code, start, end, limit,
    )
    response.headers["Cache-Control"] = "public, max-age=3600"
    return [MutualFundOut.model_validate(dict(r)) for r in rows]
