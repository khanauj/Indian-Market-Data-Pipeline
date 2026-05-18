from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_client(monkeypatch):
    """Boot the FastAPI app with fake DB/cache/scrapers, no scheduler."""
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("CACHE_ENABLED", "false")

    fake_db = AsyncMock()
    fake_db.health.return_value = {"ok": True}
    fake_db.connect.return_value = None
    fake_db.close.return_value = None

    fake_cache = AsyncMock()
    fake_cache.health.return_value = {"ok": True, "enabled": False}
    fake_cache.connect.return_value = None
    fake_cache.close.return_value = None

    with (
        patch("api.main.DBService", return_value=fake_db),
        patch("api.main.get_cache", return_value=fake_cache),
        patch("api.main.set_db"),
        patch("api.main.NSEScraper") as mock_nse,
        patch("api.main.BSEScraper") as mock_bse,
        patch("api.main.ScreenerScraper") as mock_sc,
        patch("api.main.MoneycontrolScraper") as mock_mc,
        patch("api.main.AMFIScraper") as mock_amfi,
    ):
        for m in (mock_nse, mock_bse, mock_sc, mock_mc, mock_amfi):
            inst = m.return_value
            inst.stop = AsyncMock()
            inst.health_check.return_value = {"source": "x", "circuit": "closed", "last_run_ok": False}
            inst.source = type("S", (), {"value": "x"})

        with patch("services.db_service.get_db", return_value=fake_db), \
             patch("services.cache_service.get_cache", return_value=fake_cache):
            from api.main import create_app
            app = create_app()
            with TestClient(app) as client:
                yield client


def test_health_endpoint(app_client):
    r = app_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert body["version"] == "0.1.0"
    assert "db" in body["checks"]


def test_metrics_endpoint(app_client):
    r = app_client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]


def test_openapi_lists_known_routes(app_client):
    r = app_client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    for expected in ("/health", "/stocks", "/financials/{symbol}", "/news/{symbol}",
                     "/mutual-funds", "/top-gainers", "/indices"):
        assert expected in paths


def test_admin_endpoint_requires_key(app_client):
    r = app_client.post("/admin/trigger/amfi")
    assert r.status_code == 401
