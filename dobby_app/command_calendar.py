from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from dobby_app.calendar_service import create_command_calendar_item, list_calendar_items_and_sync
from dobby_app.config import settings
from dobby_app.timeparse import parse_datetime


def create_from_text(session: Session, text: str, item_type: str) -> str:
    title, starts_at = split_title_datetime(text)
    create_command_calendar_item(
        session,
        title=title,
        starts_at=starts_at,
        item_type=item_type,
    )
    return f"Created {item_type}: {title} at {starts_at}."


def upcoming(days: int) -> str:
    tz = ZoneInfo(settings.app_timezone)
    now = datetime.now(tz)
    items = list_calendar_items_and_sync(now, now + timedelta(days=days))
    if not items:
        return "Nothing scheduled."
    return "\n".join(f"- {item['summary']} — {item['start']}" for item in items)


def split_title_datetime(text: str) -> tuple[str, datetime]:
    if " at " in text:
        title, when = text.rsplit(" at ", 1)
    elif " tomorrow " in text.lower():
        title, when = text, "tomorrow 09:00"
    else:
        raise ValueError("Use a title and time, for example: /remind Call dentist at tomorrow 9")
    return title.strip(), parse_datetime(when.strip())
