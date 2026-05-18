"""Per-source circuit breaker with closed → open → half-open transitions."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from core.config import settings
from core.exceptions import CircuitOpenException
from core.logging import get_logger
from models.enums import CircuitState

_T = TypeVar("_T")
log = get_logger("circuit_breaker")


class CircuitBreaker:
    """Trip after N consecutive failures, half-open after reset window.

    Not safe across processes (in-memory) — fine for a single worker.
    For multi-worker deploys, swap state into Redis.
    """

    def __init__(
        self,
        name: str,
        fail_threshold: int | None = None,
        reset_seconds: int | None = None,
    ) -> None:
        self.name = name
        self.fail_threshold = fail_threshold or settings.circuit_breaker_fail_threshold
        self.reset_seconds = reset_seconds or settings.circuit_breaker_reset_seconds
        self._state: CircuitState = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    def _now(self) -> float:
        return time.monotonic()

    async def _transition_to_half_open_if_due(self) -> None:
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            if self._now() - self._opened_at >= self.reset_seconds:
                self._state = CircuitState.HALF_OPEN
                log.info("circuit_half_open", source=self.name)

    async def call(self, func: Callable[[], Awaitable[_T]]) -> _T:
        async with self._lock:
            await self._transition_to_half_open_if_due()
            if self._state == CircuitState.OPEN:
                raise CircuitOpenException(
                    "circuit open", source=self.name, retry_in_s=self._retry_in()
                )

        try:
            result = await func()
        except Exception as exc:
            await self._record_failure(exc)
            raise
        else:
            await self._record_success()
            return result

    async def _record_failure(self, exc: BaseException) -> None:
        async with self._lock:
            self._consecutive_failures += 1
            if self._state == CircuitState.HALF_OPEN:
                self._open()
                log.warning(
                    "circuit_reopen_from_half_open", source=self.name, error=str(exc)
                )
            elif self._consecutive_failures >= self.fail_threshold:
                self._open()
                log.warning(
                    "circuit_opened",
                    source=self.name,
                    consecutive_failures=self._consecutive_failures,
                    error=str(exc),
                )

    async def _record_success(self) -> None:
        async with self._lock:
            if self._state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                log.info("circuit_closed", source=self.name)
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._opened_at = None

    def _open(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = self._now()

    def _retry_in(self) -> float:
        if self._opened_at is None:
            return 0.0
        return max(0.0, self.reset_seconds - (self._now() - self._opened_at))


# ─── Registry ───────────────────────────────────────────────────────
_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(name: str) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name)
    return _breakers[name]


def all_breakers() -> dict[str, CircuitBreaker]:
    return dict(_breakers)
