from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import AsyncMock

import httpx
import pytest

from models.enums import ScraperSource
from scrapers.base import BaseScraper, random_user_agent


class _DummyScraper(BaseScraper):
    source: ClassVar[ScraperSource] = ScraperSource.AMFI

    async def fetch(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return [{"x": 1}]

    async def normalize(self, raw: list[dict[str, Any]]) -> list[Any]:
        return raw

    async def save(self, records: list[Any]) -> tuple[int, int]:
        return len(records), 0


class TestUserAgentRotation:
    def test_returns_a_realistic_ua(self):
        ua = random_user_agent()
        assert "Mozilla/5.0" in ua


@pytest.mark.asyncio
class TestBaseRun:
    async def test_run_writes_run_log_and_checkpoint(self, fake_db):
        s = _DummyScraper(fake_db)
        result = await s.run()
        assert result["status"] == "success"
        assert result["inserted"] == 1
        fake_db.log_scraper_run.assert_awaited_once()
        fake_db.update_checkpoint.assert_awaited_once()

    async def test_run_handles_fetch_failure(self, fake_db, monkeypatch):
        s = _DummyScraper(fake_db)

        async def _boom(*a, **kw):
            raise RuntimeError("upstream down")

        monkeypatch.setattr(s, "fetch", _boom)
        result = await s.run()
        assert result["status"] == "failed"
        assert "RuntimeError" in result["error"]
        fake_db.log_scraper_run.assert_awaited_once()
