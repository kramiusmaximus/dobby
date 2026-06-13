from __future__ import annotations

from datetime import datetime

from dobby_app.integrations.caldav import list_items
from dobby_app.services.memory import sync_calendar_snapshot_to_memory


def list_calendar_items_and_sync(
    starts_at: datetime,
    ends_at: datetime,
    calendar_name: str | None = None,
) -> list[dict]:
    items = list_items(starts_at, ends_at, calendar_name=calendar_name)
    sync_calendar_snapshot_to_memory(items)
    return items
