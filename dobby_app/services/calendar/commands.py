from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from dobby_app.db.models import CaldavItem
from dobby_app.integrations.caldav import create_calendar_item
from dobby_app.services.memory import sync_calendar_item_to_memory


def create_command_calendar_item(
    session: Session,
    *,
    title: str,
    starts_at: datetime,
    item_type: str,
) -> CaldavItem:
    memory_page = sync_calendar_item_to_memory(title=title, starts_at=starts_at, item_type=item_type)
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
        memory_page=memory_page,
    )
    session.add(item)
    return item
