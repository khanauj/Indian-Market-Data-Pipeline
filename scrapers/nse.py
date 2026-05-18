"""NSE India scraper.

NSE's "public" API requires:
  1. Warm a session via a browser-like GET to https://www.nseindia.com/
     so the server sets nseappid + bm_sv cookies in the AsyncClient cookiejar.
  2. Re-warm whenever the API returns 401/403 ("session expired").

All endpoints return JSON. We flatten nested rows into Pydantic models.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, ClassVar

from core.exceptions import ScraperException, SessionExpiredError
from models.enums import Exchange, MoverType, ScraperSource
from models.schemas import MarketIndexIn, StockPriceIn, TopMoverIn
from scrapers.base import BaseScraper
from services.cache_service import get_cache
from services.normalization import normalize_datetime, normalize_symbol

NSE_HOME = "https://www.nseindia.com/"
NSE_API = "https://www.nseindia.com/api"


class NSEScraper(BaseScraper):
    source: ClassVar[ScraperSource] = ScraperSource.NSE

    def __init__(self, *a: Any, **kw: Any) -> None:
        super().__init__(*a, **kw)
        self._session_warm = False

    def _default_headers(self) -> dict[str, str]:
        h = super()._default_headers()
        h.update({
            "Referer": "https://www.nseindia.com/",
            "Origin": "https://www.nseindia.com",
            "X-Requested-With": "XMLHttpRequest",
        })
        return h

    async def _warm_session(self) -> None:
        """Hit the homepage to populate the cookiejar before API calls."""
        await self.start()
        try:
            r = await self.client.get(NSE_HOME)
            r.raise_for_status()
            # Some NSE endpoints want a second hit to /market-data/live-equity-market
            await self.client.get(f"{NSE_HOME}market-data/live-equity-market")
            self._session_warm = True
            self.log.debug("nse_session_warm_ok", cookies=len(self.client.cookies.jar))
        except Exception as e:  # noqa: BLE001
            self._session_warm = False
            raise ScraperException("nse session warm failed", error=str(e)) from e

    async def _ensure_session(self) -> None:
        if not self._session_warm:
            await self._warm_session()

    async def _api_get(self, path: str, endpoint_label: str) -> Any:
        await self._ensure_session()
        url = f"{NSE_API}{path}"
        try:
            return await self.get_json(url, endpoint_label=endpoint_label)
        except ScraperException as e:
            # Force re-warm once and retry
            self.log.info("nse_session_retry", endpoint=endpoint_label, error=str(e))
            self._session_warm = False
            await self._warm_session()
            return await self.get_json(url, endpoint_label=endpoint_label)

    # ═══════════════════════════════════════════════════════════════
    # Tasks (dispatched from BaseScraper.run via the `task` arg)
    # ═══════════════════════════════════════════════════════════════
    async def fetch(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        task = (args[0] if args else kwargs.get("task")) or "prices"
        return await {
            "prices": self._fetch_prices,
            "gainers_losers": self._fetch_gainers_losers,
            "indices": self._fetch_indices,
        }[task]()

    async def _fetch_prices(self) -> list[dict[str, Any]]:
        cache = get_cache()
        cached = await cache.get("nse:nifty50")
        payload = cached or await self._api_get(
            "/equity-stockIndices?index=NIFTY%2050", endpoint_label="equity-stockIndices"
        )
        if cached is None:
            await cache.set("nse:nifty50", payload, ttl=240)

        rows = payload.get("data", []) if isinstance(payload, dict) else []
        ts = normalize_datetime(payload.get("timestamp")) or datetime.now(tz=timezone.utc)
        out: list[dict[str, Any]] = []
        for r in rows:
            if r.get("symbol") in (None, "NIFTY 50"):
                continue
            out.append({
                "_table": "prices",
                "symbol": r.get("symbol"),
                "open": r.get("open"),
                "high": r.get("dayHigh"),
                "low": r.get("dayLow"),
                "close": r.get("previousClose"),
                "ltp": r.get("lastPrice"),
                "volume": r.get("totalTradedVolume"),
                "timestamp": ts,
            })
        return out

    async def _fetch_gainers_losers(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        ts = datetime.now(tz=timezone.utc)
        for which in ("gainers", "losers"):
            payload = await self._api_get(
                f"/live-analysis-variations?index={which}",
                endpoint_label=f"variations-{which}",
            )
            section = payload.get("NIFTY", {}) if isinstance(payload, dict) else {}
            for r in section.get("data", []):
                out.append({
                    "_table": "movers",
                    "type": MoverType.GAINER.value if which == "gainers" else MoverType.LOSER.value,
                    "symbol": r.get("symbol"),
                    "ltp": r.get("ltp") or r.get("lastPrice"),
                    "change_pct": r.get("perChange") or r.get("pChange"),
                    "volume": r.get("tradedQuantity") or r.get("totalTradedVolume"),
                    "timestamp": ts,
                })
        return out

    async def _fetch_indices(self) -> list[dict[str, Any]]:
        payload = await self._api_get("/allIndices", endpoint_label="allIndices")
        ts = normalize_datetime(payload.get("timestamp")) or datetime.now(tz=timezone.utc)
        out: list[dict[str, Any]] = []
        for r in payload.get("data", []):
            out.append({
                "_table": "indices",
                "index_name": r.get("indexSymbol") or r.get("index"),
                "open": r.get("open"),
                "high": r.get("high"),
                "low": r.get("low"),
                "close": r.get("last") or r.get("previousClose"),
                "change_pct": r.get("percentChange"),
                "advances": r.get("advances"),
                "declines": r.get("declines"),
                "timestamp": ts,
            })
        return out

    # ═══════════════════════════════════════════════════════════════
    # Normalize
    # ═══════════════════════════════════════════════════════════════
    async def normalize(self, raw: list[dict[str, Any]]) -> list[Any]:
        out: list[Any] = []
        for r in raw:
            table = r.get("_table")
            try:
                if table == "prices":
                    sym = normalize_symbol(r.get("symbol"))
                    if not sym:
                        continue
                    out.append(StockPriceIn(
                        symbol=sym,
                        open=_num(r.get("open")), high=_num(r.get("high")),
                        low=_num(r.get("low")), close=_num(r.get("close")),
                        ltp=_num(r.get("ltp")), volume=_int(r.get("volume")),
                        timestamp=r["timestamp"],
                    ))
                elif table == "movers":
                    sym = normalize_symbol(r.get("symbol"))
                    if not sym:
                        continue
                    out.append(TopMoverIn(
                        symbol=sym, type=r["type"],
                        ltp=float(r.get("ltp") or 0.0),
                        change_pct=float(r.get("change_pct") or 0.0),
                        volume=_int(r.get("volume")),
                        timestamp=r["timestamp"],
                    ))
                elif table == "indices":
                    name = (r.get("index_name") or "").strip()
                    if not name:
                        continue
                    out.append(MarketIndexIn(
                        index_name=name,
                        open=_num(r.get("open")), high=_num(r.get("high")),
                        low=_num(r.get("low")), close=_num(r.get("close")),
                        change_pct=_num(r.get("change_pct")),
                        advances=_int(r.get("advances")),
                        declines=_int(r.get("declines")),
                        timestamp=r["timestamp"],
                    ))
            except Exception:  # noqa: BLE001
                self.log.warning("nse_row_skipped", raw=r, exc_info=False)
        return out

    # ═══════════════════════════════════════════════════════════════
    # Save — dispatch by model type
    # ═══════════════════════════════════════════════════════════════
    async def save(self, records: list[Any]) -> tuple[int, int]:
        if not records:
            return 0, 0
        prices = [r for r in records if isinstance(r, StockPriceIn)]
        movers = [r for r in records if isinstance(r, TopMoverIn)]
        indices = [r for r in records if isinstance(r, MarketIndexIn)]

        inserted = 0
        if prices:
            ins, _ = await self.db.upsert_batch(
                "stock_prices", prices,
                conflict_cols=["symbol", "timestamp"],
            )
            inserted += ins
        if movers:
            ins, _ = await self.db.upsert_batch(
                "top_gainers_losers", movers,
                conflict_cols=["symbol", "type", "timestamp"],
            )
            inserted += ins
        if indices:
            ins, _ = await self.db.upsert_batch(
                "market_indices", indices,
                conflict_cols=["index_name", "timestamp"],
            )
            inserted += ins
        return inserted, 0


# ─── Tiny coercers ────────────────────────────────────────────────
def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _int(v: Any) -> int | None:
    n = _num(v)
    return int(n) if n is not None else None
