from __future__ import annotations

from enum import StrEnum


class Exchange(StrEnum):
    NSE = "NSE"
    BSE = "BSE"
    BOTH = "BOTH"


class PeriodType(StrEnum):
    QUARTERLY = "Q"
    ANNUAL = "A"
    TTM = "TTM"


class FilingType(StrEnum):
    BOARD_MEETING = "BOARD_MEETING"
    CORPORATE_ACTION = "CORPORATE_ACTION"
    DIVIDEND = "DIVIDEND"
    BONUS = "BONUS"
    SPLIT = "SPLIT"
    RIGHTS = "RIGHTS"
    BUYBACK = "BUYBACK"
    SHAREHOLDING = "SHAREHOLDING"
    RESULTS = "RESULTS"
    ANNUAL_REPORT = "ANNUAL_REPORT"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    OTHER = "OTHER"


class MoverType(StrEnum):
    GAINER = "gainer"
    LOSER = "loser"


class ScraperSource(StrEnum):
    NSE = "nse"
    BSE = "bse"
    SCREENER = "screener"
    MONEYCONTROL = "moneycontrol"
    AMFI = "amfi"


class ScraperStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
