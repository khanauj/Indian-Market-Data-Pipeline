"""Async Redis cache wrapper.

Soft-fail: if Redis is unavailable, falls through to source-of-truth.
Never raises on cache errors — logs and returns None (or no-ops on set).
"""
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis
from redis.exceptions import RedisError

from core.config import settings
from core.logging import get_logger

log = get_logger("cache")


class CacheService:
    def __init__(self, url: str | None = None, default_ttl: int | None = None) -> None:
        self._url = url or settings.redis_url_str
        self._ttl = default_ttl or settings.redis_default_ttl
        self._enabled = settings.cache_enabled
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        if not self._enabled:
            return
        self._client = redis.from_url(
            self._url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
        try:
            await self._client.ping()
            log.info("redis_connected", url=self._url)
        except RedisError as e:
            log.warning("redis_unavailable", error=str(e))
            self._client = None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get(self, key: str) -> Any:
        if not self._enabled or self._client is None:
            return None
        try:
            raw = await self._client.get(key)
            return json.loads(raw) if raw is not None else None
        except (RedisError, json.JSONDecodeError) as e:
            log.warning("cache_get_failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        if not self._enabled or self._client is None:
            return False
        try:
            await self._client.set(key, json.dumps(value, default=str), ex=ttl or self._ttl)
            return True
        except (RedisError, TypeError) as e:
            log.warning("cache_set_failed", key=key, error=str(e))
            return False

    async def delete(self, *keys: str) -> int:
        if not self._enabled or self._client is None or not keys:
            return 0
        try:
            return int(await self._client.delete(*keys))
        except RedisError as e:
            log.warning("cache_delete_failed", error=str(e))
            return 0

    async def invalidate_pattern(self, pattern: str) -> int:
        """SCAN-based invalidation; safe on large keyspaces."""
        if not self._enabled or self._client is None:
            return 0
        deleted = 0
        try:
            async for key in self._client.scan_iter(match=pattern, count=200):
                deleted += int(await self._client.delete(key))
            return deleted
        except RedisError as e:
            log.warning("cache_invalidate_failed", pattern=pattern, error=str(e))
            return deleted

    async def health(self) -> dict[str, Any]:
        if not self._enabled:
            return {"enabled": False, "ok": True}
        if self._client is None:
            return {"enabled": True, "ok": False, "reason": "not_connected"}
        try:
            await self._client.ping()
            return {"enabled": True, "ok": True}
        except RedisError as e:
            return {"enabled": True, "ok": False, "reason": str(e)}


# ─── Module-level singleton (set in lifespan) ──────────────────────
_cache: CacheService | None = None


def get_cache() -> CacheService:
    global _cache
    if _cache is None:
        _cache = CacheService()
    return _cache
