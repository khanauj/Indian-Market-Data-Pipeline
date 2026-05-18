from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from api.dependencies import db_dep
from models.schemas import MarketIndexOut, TopMoverOut
from services.storage import Storage

router = APIRouter(prefix="", tags=["market"])


@router.get("/top-gainers", response_model=list[TopMoverOut])
async def top_gainers(
    response: Response,
    limit: int = Query(20, ge=1, le=200),
    db: Storage = Depends(db_dep),
) -> list[TopMoverOut]:
    rows = await db.fetch(
        """SELECT * FROM (
              SELECT *,
                     ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY timestamp DESC) AS rn
              FROM top_gainers_losers
              WHERE type = 'gainer'
           ) WHERE rn = 1
           ORDER BY change_pct DESC
           LIMIT $1""",
        limit,
    )
    response.headers["Cache-Control"] = "public, max-age=30"
    return [TopMoverOut.model_validate({k: v for k, v in dict(r).items() if k != "rn"}) for r in rows]


@router.get("/top-losers", response_model=list[TopMoverOut])
async def top_losers(
    response: Response,
    limit: int = Query(20, ge=1, le=200),
    db: Storage = Depends(db_dep),
) -> list[TopMoverOut]:
    rows = await db.fetch(
        """SELECT * FROM (
              SELECT *,
                     ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY timestamp DESC) AS rn
              FROM top_gainers_losers
              WHERE type = 'loser'
           ) WHERE rn = 1
           ORDER BY change_pct ASC
           LIMIT $1""",
        limit,
    )
    response.headers["Cache-Control"] = "public, max-age=30"
    return [TopMoverOut.model_validate({k: v for k, v in dict(r).items() if k != "rn"}) for r in rows]


@router.get("/indices", response_model=list[MarketIndexOut])
async def list_indices(
    response: Response,
    db: Storage = Depends(db_dep),
) -> list[MarketIndexOut]:
    rows = await db.fetch("SELECT * FROM v_latest_index_snapshot")
    response.headers["Cache-Control"] = "public, max-age=30"
    return [MarketIndexOut.model_validate(dict(r)) for r in rows]
