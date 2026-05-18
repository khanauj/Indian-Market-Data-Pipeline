"""FastAPI app — lifespan boots DB pool, Redis, scrapers, scheduler."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import APIRouter, Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from api.dependencies import admin_auth, cache_dep, db_dep
from api.routers import financials, market, mutual_funds, news, stocks
from core.config import settings
from core.logging import configure_logging, get_logger
from models.schemas import HealthResponse
from scrapers import (
    AMFIScraper,
    BSEScraper,
    MoneycontrolScraper,
    NSEScraper,
    ScreenerScraper,
)
from services.cache_service import CacheService, get_cache
from services.circuit_breaker import all_breakers
from services.scheduler import build_scheduler
from services.storage import Storage, get_storage, set_storage

log = get_logger("api")
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    storage = get_storage()
    await storage.connect()
    set_storage(storage)
    log.info("storage_ready", backend=settings.storage_backend)

    cache = get_cache()
    await cache.connect()

    nse = NSEScraper(storage)
    bse = BSEScraper(storage)
    screener = ScreenerScraper(storage)
    moneycontrol = MoneycontrolScraper(storage)
    amfi = AMFIScraper(storage)
    app.state.scrapers = {
        "nse": nse, "bse": bse, "screener": screener,
        "moneycontrol": moneycontrol, "amfi": amfi,
    }

    scheduler = None
    if settings.scheduler_enabled:
        scheduler = build_scheduler(nse, bse, screener, moneycontrol, amfi)
        scheduler.start()
        app.state.scheduler = scheduler
        log.info("scheduler_started")
    else:
        app.state.scheduler = None
        log.info("scheduler_disabled")

    log.info("app_ready", env=settings.env)
    try:
        yield
    finally:
        log.info("app_shutdown_begin")
        if scheduler is not None:
            scheduler.shutdown(wait=True)
            log.info("scheduler_stopped")
        for s in app.state.scrapers.values():
            try:
                await s.stop()
            except Exception:  # noqa: BLE001
                log.error("scraper_stop_failed", source=s.source.value, exc_info=True)
        await cache.close()
        await storage.close()
        log.info("app_shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Indian Market Data Pipeline",
        description="CMOTS-alternative: NSE / BSE / Screener / Moneycontrol / AMFI",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # ─── Health & metrics ───────────────────────────────────────────
    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health(
        db: Storage = Depends(db_dep),
        cache: CacheService = Depends(cache_dep),
    ) -> HealthResponse:
        db_health = await db.health()
        cache_health = await cache.health()
        breaker_health = {
            name: {"state": b.state.value} for name, b in all_breakers().items()
        }
        scraper_health = {
            name: s.health_check() for name, s in app.state.scrapers.items()
        }
        overall = "ok" if db_health["ok"] and cache_health.get("ok", True) else "degraded"
        return HealthResponse(
            status=overall,
            version=app.version,
            env=settings.env,
            checks={
                "db": db_health,
                "cache": cache_health,
                "breakers": breaker_health,
                "scrapers": scraper_health,
            },
        )

    @app.get("/metrics", tags=["system"], include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # ─── Admin ──────────────────────────────────────────────────────
    admin = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(admin_auth)])

    @admin.post("/trigger/{scraper}")
    async def trigger_scraper(scraper: str, task: str | None = None) -> dict[str, object]:
        scrapers = app.state.scrapers
        if scraper not in scrapers:
            return {"ok": False, "error": f"unknown scraper '{scraper}'", "available": list(scrapers)}
        result = await scrapers[scraper].run(task) if task else await scrapers[scraper].run()
        return {"ok": True, "result": result}

    app.include_router(admin)

    # ─── Domain routers ─────────────────────────────────────────────
    app.include_router(stocks.router)
    app.include_router(financials.router)
    app.include_router(news.router)
    app.include_router(mutual_funds.router)
    app.include_router(market.router)

    return app


app = create_app()
