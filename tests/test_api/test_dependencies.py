from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.dependencies import admin_auth
from core.config import settings


def test_admin_auth_rejects_missing():
    with pytest.raises(HTTPException) as exc:
        admin_auth(x_admin_key=None)
    assert exc.value.status_code == 401


def test_admin_auth_rejects_wrong():
    with pytest.raises(HTTPException) as exc:
        admin_auth(x_admin_key="not-the-key")
    assert exc.value.status_code == 401


def test_admin_auth_accepts_correct():
    admin_auth(x_admin_key=settings.admin_api_key.get_secret_value())
