from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import dateparser

from dobby_app.core.config import settings


def parse_datetime(text: str) -> datetime:
    tz = ZoneInfo(settings.app_timezone)
    parsed = dateparser.parse(
        text,
        settings={
            "TIMEZONE": settings.app_timezone,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
        },
    )
    if not parsed:
        raise ValueError(f"Could not understand date/time: {text}")
    return parsed.astimezone(tz)
