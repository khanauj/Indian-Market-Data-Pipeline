from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.scheduler import is_market_hours

IST = ZoneInfo("Asia/Kolkata")


@pytest.mark.parametrize(
    ("dt", "expected"),
    [
        # Weekday open
        (datetime(2026, 5, 15, 10, 30, tzinfo=IST), True),
        # Weekday pre-open
        (datetime(2026, 5, 15, 8, 0, tzinfo=IST), False),
        # Weekday post-close
        (datetime(2026, 5, 15, 16, 0, tzinfo=IST), False),
        # Saturday during market hours-equivalent
        (datetime(2026, 5, 16, 10, 30, tzinfo=IST), False),
        # Sunday
        (datetime(2026, 5, 17, 10, 30, tzinfo=IST), False),
        # Exactly at open
        (datetime(2026, 5, 15, 9, 15, tzinfo=IST), True),
        # Exactly at close
        (datetime(2026, 5, 15, 15, 30, tzinfo=IST), True),
    ],
)
def test_market_hours_window(dt, expected):
    assert is_market_hours(dt) == expected
