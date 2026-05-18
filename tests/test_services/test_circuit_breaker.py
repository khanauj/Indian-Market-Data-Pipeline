from __future__ import annotations

import asyncio

import pytest

from core.exceptions import CircuitOpenException
from models.enums import CircuitState
from services.circuit_breaker import CircuitBreaker


async def _success() -> str:
    return "ok"


async def _fail() -> str:
    raise RuntimeError("boom")


class TestCircuitBreaker:
    async def test_closed_passes_calls_through(self):
        cb = CircuitBreaker("t", fail_threshold=3, reset_seconds=10)
        assert await cb.call(_success) == "ok"
        assert cb.state == CircuitState.CLOSED

    async def test_opens_after_threshold(self):
        cb = CircuitBreaker("t", fail_threshold=2, reset_seconds=10)
        with pytest.raises(RuntimeError):
            await cb.call(_fail)
        assert cb.state == CircuitState.CLOSED
        with pytest.raises(RuntimeError):
            await cb.call(_fail)
        assert cb.state == CircuitState.OPEN

    async def test_open_rejects_fast(self):
        cb = CircuitBreaker("t", fail_threshold=1, reset_seconds=10)
        with pytest.raises(RuntimeError):
            await cb.call(_fail)
        assert cb.state == CircuitState.OPEN
        with pytest.raises(CircuitOpenException):
            await cb.call(_success)

    async def test_half_open_after_reset(self):
        cb = CircuitBreaker("t", fail_threshold=1, reset_seconds=0)
        with pytest.raises(RuntimeError):
            await cb.call(_fail)
        await asyncio.sleep(0.01)
        # Reset window has elapsed → next call transitions to HALF_OPEN, then to CLOSED on success
        assert await cb.call(_success) == "ok"
        assert cb.state == CircuitState.CLOSED

    async def test_half_open_failure_reopens(self):
        cb = CircuitBreaker("t", fail_threshold=1, reset_seconds=0)
        with pytest.raises(RuntimeError):
            await cb.call(_fail)
        await asyncio.sleep(0.01)
        with pytest.raises(RuntimeError):
            await cb.call(_fail)
        assert cb.state == CircuitState.OPEN
