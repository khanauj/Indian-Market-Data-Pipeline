"""FastAPI dependencies — DB, cache, admin auth."""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from core.config import settings
from services.cache_service import CacheService, get_cache
from services.storage import Storage, get_storage


def db_dep() -> Storage:
    return get_storage()


def cache_dep() -> CacheService:
    return get_cache()


def admin_auth(x_admin_key: str | None = Header(default=None)) -> None:
    expected = settings.admin_api_key.get_secret_value()
    if not x_admin_key or x_admin_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid admin key",
            headers={"WWW-Authenticate": "Header X-Admin-Key"},
        )
