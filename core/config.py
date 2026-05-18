from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── App ────────────────────────────────────────────────────────
    env: Literal["development", "test", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    tz: str = "Asia/Kolkata"

    # ─── API ────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 2
    admin_api_key: SecretStr = SecretStr("change-me")

    # ─── Supabase ───────────────────────────────────────────────────
    supabase_url: str = "http://localhost:54321"
    supabase_service_role_key: SecretStr = SecretStr("")
    supabase_anon_key: SecretStr = SecretStr("")

    # ─── Storage backend ────────────────────────────────────────────
    # "sqlite"   — local file, no external deps (default)
    # "supabase" — Supabase Postgres via asyncpg
    # "both"     — tee writes to both (reads served from Supabase)
    storage_backend: Literal["sqlite", "supabase", "both"] = "sqlite"
    sqlite_path: str = "data/market.sqlite"

    # ─── Database (Postgres / Supabase) ────────────────────────────
    # Plain str (not PostgresDsn) so an unset/placeholder URL doesn't crash
    # startup when STORAGE_BACKEND=sqlite. Validated when the backend actually
    # tries to connect.
    database_url: str = "postgresql://postgres:postgres@localhost:5432/postgres"
    database_pool_min: int = 5
    database_pool_max: int = 20

    # ─── Redis ──────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_default_ttl: int = 240
    cache_enabled: bool = True

    # ─── HTTP / scraper ─────────────────────────────────────────────
    http_timeout_seconds: float = 30.0
    http_max_retries: int = 4
    http_rate_limit_per_source_ms: int = 500
    scraper_concurrency: int = 10
    proxy_url: str | None = None
    proxy_rotate_on_block: bool = True

    # ─── Playwright ─────────────────────────────────────────────────
    playwright_headless: bool = True
    playwright_locale: str = "en-IN"
    playwright_timezone: str = "Asia/Kolkata"
    playwright_viewport_width: int = 1920
    playwright_viewport_height: int = 1080

    # ─── Circuit breaker ────────────────────────────────────────────
    circuit_breaker_fail_threshold: int = 3
    circuit_breaker_reset_seconds: int = 60

    # ─── Scheduler ──────────────────────────────────────────────────
    scheduler_enabled: bool = True
    screener_batch_size: int = 50

    # ─── Observability ──────────────────────────────────────────────
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    alert_webhook_url: str | None = None
    sentry_dsn: str | None = None

    @field_validator("database_url", mode="before")
    @classmethod
    def _coerce_db_url(cls, v: str) -> str:
        # Supabase pooler / asyncpg require postgresql:// scheme (not postgres://)
        s = str(v)
        return s.replace("postgres://", "postgresql://", 1) if s.startswith("postgres://") else s

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_test(self) -> bool:
        return self.env == "test"

    @property
    def database_url_str(self) -> str:
        return self.database_url

    @property
    def redis_url_str(self) -> str:
        return self.redis_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Module-level singleton; tests should call get_settings.cache_clear() before re-reading env.
settings = get_settings()
