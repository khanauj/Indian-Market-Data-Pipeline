"""BaseScraper — the contract every source must implement."""
from __future__ import annotations

import asyncio
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, ClassVar

import httpx
from prometheus_client import Counter, Histogram
from pydantic import BaseModel
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.config import settings
from core.exceptions import (
    AntibotBlockError,
    CircuitOpenException,
    RateLimitError,
    ScraperException,
)
from core.logging import get_logger
from models.enums import ScraperSource, ScraperStatus
from services.circuit_breaker import get_breaker
from services.storage import Storage

# ─── User-Agent pool (curated, recent desktop browsers) ────────────
_USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
)


def random_user_agent() -> str:
    return random.choice(_USER_AGENTS)


# ─── Prometheus metrics (module-level singletons) ──────────────────
class ScraperMetrics:
    requests = Counter(
        "scraper_requests_total",
        "Scraper HTTP requests",
        ["source", "endpoint", "status"],
    )
    duration = Histogram(
        "scraper_duration_seconds",
        "Scraper run duration",
        ["source", "task"],
    )
    records = Counter(
        "scraper_records_total",
        "Records ingested by scrapers",
        ["source", "table", "outcome"],  # outcome = inserted | skipped | failed
    )
    failures = Counter(
        "scraper_failures_total",
        "Scraper run-level failures",
        ["source", "reason"],
    )


# ─── Per-source rate limiter ───────────────────────────────────────
class _RateLimiter:
    """Token-bucket-lite: ensures min interval between successive acquires."""

    def __init__(self, interval_ms: int) -> None:
        self._interval = interval_ms / 1000.0
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._interval - (now - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


# ─── Base contract ─────────────────────────────────────────────────
class BaseScraper(ABC):
    source: ClassVar[ScraperSource]

    def __init__(self, db: Storage) -> None:
        self.db = db
        self.log = get_logger(f"scraper.{self.source.value}")
        self._breaker = get_breaker(self.source.value)
        self._rate_limiter = _RateLimiter(settings.http_rate_limit_per_source_ms)
        self._client: httpx.AsyncClient | None = None
        self._last_run_ok = False

    # ─── Lifecycle ──────────────────────────────────────────────────
    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.http_timeout_seconds),
                follow_redirects=True,
                headers=self._default_headers(),
                proxy=settings.proxy_url or None,
            )

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise ScraperException("scraper client not started", source=self.source.value)
        return self._client

    def _default_headers(self) -> dict[str, str]:
        return {
            "User-Agent": random_user_agent(),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }

    # ─── Retryable GET ──────────────────────────────────────────────
    async def get_json(
        self, url: str, *, endpoint_label: str | None = None, **kwargs: Any
    ) -> Any:
        return await self._get(url, endpoint_label=endpoint_label, kind="json", **kwargs)

    async def get_text(
        self, url: str, *, endpoint_label: str | None = None, **kwargs: Any
    ) -> str:
        return await self._get(url, endpoint_label=endpoint_label, kind="text", **kwargs)

    async def _get(
        self,
        url: str,
        *,
        endpoint_label: str | None,
        kind: str,
        **kwargs: Any,
    ) -> Any:
        label = endpoint_label or url
        await self._rate_limiter.acquire()

        async def _call() -> Any:
            r = await self.client.get(url, **kwargs)
            ScraperMetrics.requests.labels(self.source.value, label, str(r.status_code)).inc()
            if r.status_code == 429:
                raise RateLimitError("429 from upstream", source=self.source.value, url=url)
            if r.status_code in (403, 503) and "cloudflare" in r.text.lower()[:512]:
                raise AntibotBlockError("cloudflare block", source=self.source.value, url=url)
            r.raise_for_status()
            return r.json() if kind == "json" else r.text

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(settings.http_max_retries),
                wait=wait_exponential(multiplier=1, min=1, max=30),
                retry=retry_if_exception_type(
                    (httpx.TimeoutException, httpx.HTTPStatusError, RateLimitError)
                ),
                reraise=True,
            ):
                with attempt:
                    return await self._breaker.call(_call)
        except CircuitOpenException:
            ScraperMetrics.failures.labels(self.source.value, "circuit_open").inc()
            raise
        except RetryError as e:
            ScraperMetrics.failures.labels(self.source.value, "retry_exhausted").inc()
            raise ScraperException(
                "retries exhausted", source=self.source.value, url=url, cause=str(e)
            ) from e

    # ─── Abstract contract ──────────────────────────────────────────
    @abstractmethod
    async def fetch(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def normalize(
        self, raw: list[dict[str, Any]]
    ) -> list[BaseModel]: ...

    @abstractmethod
    async def save(self, records: list[BaseModel]) -> tuple[int, int]: ...

    # ─── Orchestrator ───────────────────────────────────────────────
    async def run(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        started_at = datetime.now(tz=timezone.utc)
        task = kwargs.get("task") or (args[0] if args else "default")
        labels = {"source": self.source.value, "task": str(task)}

        await self.start()
        inserted = skipped = 0
        status: ScraperStatus = ScraperStatus.SUCCESS
        err_msg: str | None = None

        try:
            with ScraperMetrics.duration.labels(**labels).time():
                raw = await self.fetch(*args, **kwargs)
                if not raw:
                    status = ScraperStatus.SKIPPED
                    self.log.info("no_records", task=task)
                else:
                    models = await self.normalize(raw)
                    inserted, skipped = await self.save(models)
                    ScraperMetrics.records.labels(
                        self.source.value, str(task), "inserted"
                    ).inc(inserted)
                    ScraperMetrics.records.labels(
                        self.source.value, str(task), "skipped"
                    ).inc(skipped)
                    self.log.info("run_ok", task=task, inserted=inserted, skipped=skipped)
            self._last_run_ok = True
        except CircuitOpenException as e:
            status = ScraperStatus.SKIPPED
            err_msg = str(e)
            self._last_run_ok = False
            self.log.warning("run_skipped_circuit_open", task=task, error=err_msg)
        except Exception as e:  # noqa: BLE001
            status = ScraperStatus.FAILED
            err_msg = f"{type(e).__name__}: {e}"
            self._last_run_ok = False
            ScraperMetrics.failures.labels(self.source.value, type(e).__name__).inc()
            self.log.error("run_failed", task=task, error=err_msg, exc_info=True)
        finally:
            ended_at = datetime.now(tz=timezone.utc)
            try:
                await self.db.log_scraper_run(
                    source=self.source,
                    status=status,
                    started_at=started_at,
                    ended_at=ended_at,
                    records_inserted=inserted,
                    records_skipped=skipped,
                    error_msg=err_msg,
                )
                await self.db.update_checkpoint(
                    source=self.source,
                    last_run_at=ended_at,
                    last_success_at=ended_at if status == ScraperStatus.SUCCESS else None,
                )
            except Exception:  # noqa: BLE001
                self.log.error("run_log_failed", exc_info=True)

        return {
            "source": self.source.value,
            "task": task,
            "status": status.value,
            "inserted": inserted,
            "skipped": skipped,
            "error": err_msg,
            "duration_s": (ended_at - started_at).total_seconds(),
        }

    # ─── Health ─────────────────────────────────────────────────────
    def health_check(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "circuit": self._breaker.state.value,
            "last_run_ok": self._last_run_ok,
        }
