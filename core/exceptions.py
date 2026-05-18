from __future__ import annotations

from typing import Any


class PipelineException(Exception):
    """Root of the pipeline exception hierarchy."""

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context = context

    def __str__(self) -> str:
        if not self.context:
            return self.message
        ctx = " ".join(f"{k}={v!r}" for k, v in self.context.items())
        return f"{self.message} | {ctx}"


# ─── Scraper layer ──────────────────────────────────────────────────
class ScraperException(PipelineException):
    """Generic fetch failure (network, parse, upstream 5xx)."""


class RateLimitError(ScraperException):
    """Upstream returned 429 or equivalent throttle signal."""


class AntibotBlockError(ScraperException):
    """Cloudflare / WAF block detected — trigger proxy rotation."""


class SessionExpiredError(ScraperException):
    """Cookie / token no longer valid — re-warm session."""


# ─── Normalization ──────────────────────────────────────────────────
class NormalizationException(PipelineException):
    """Field could not be parsed into the expected type."""


# ─── Database ───────────────────────────────────────────────────────
class DatabaseException(PipelineException):
    """Write or read against the database failed."""


class DuplicateRecordError(DatabaseException):
    """UNIQUE violation that wasn't absorbed by ON CONFLICT."""


# ─── Circuit breaker ────────────────────────────────────────────────
class CircuitOpenException(PipelineException):
    """Source is isolated by the circuit breaker; call rejected fast."""
