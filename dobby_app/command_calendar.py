from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from dobby_app.caldav_client import create_calendar_item, list_items
from dobby_app.config import settings
from dobby_app.models import CaldavItem
from dobby_app.timeparse import parse_datetime
from dobby_app.wiki_memory import sync_calendar_item_to_wiki, sync_calendar_snapshot_to_wiki


def create_from_text(session: Session, text: str, item_type: str) -> str:
    title, starts_at = split_title_datetime(text)
    wiki_page = sync_calendar_item_to_wiki(title=title, starts_at=starts_at, item_type=item_type)
    result = create_calendar_item(
        title=title,
        starts_at=starts_at,
        item_type=item_type,
        alarm_minutes_before=0 if item_type == "reminder" else None,
    )
    item = CaldavItem(
        uid=result.uid,
        calendar_url=result.url,
        title=title,
        item_type=item_type,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=15),
        alarm_minutes_before=0 if item_type == "reminder" else None,
        wiki_page=wiki_page,
    )
    session.add(item)
    return f"Created {item_type}: {title} at {starts_at}."


def upcoming(days: int) -> str:
    tz = ZoneInfo(settings.app_timezone)
    now = datetime.now(tz)
    items = list_items(now, now + timedelta(days=days))
    sync_calendar_snapshot_to_wiki(items)
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
