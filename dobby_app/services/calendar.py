from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from dobby_app.integrations.caldav import create_calendar_item, delete_calendar_item, list_items, update_calendar_item
from dobby_app.db.session import session_scope
from dobby_app.db.repositories.calendar_items import (
    stored_alarm_minutes_before,
    try_delete_caldav_record,
    try_update_caldav_record,
)
from dobby_app.db.models import CaldavItem
from dobby_app.services.memory_notes import sync_calendar_item_to_memory, sync_calendar_snapshot_to_memory


def list_calendar_items_and_sync(
    starts_at: datetime,
    ends_at: datetime,
    calendar_name: str | None = None,
) -> list[dict]:
    items = list_items(starts_at, ends_at, calendar_name=calendar_name)
    sync_calendar_snapshot_to_memory(items)
    return items


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


def create_execution_calendar_item(
    *,
    title: str,
    starts_at: datetime,
    item_type: str,
    alarm_minutes_before: int | None,
    duration_minutes: int | None,
    calendar_name: str | None,
) -> str:
    with session_scope() as session:
        result = create_calendar_item(
            title=title,
            starts_at=starts_at,
            duration_minutes=duration_minutes or 15,
            item_type=item_type,
            alarm_minutes_before=alarm_minutes_before,
            calendar_name=calendar_name,
        )
        session.add(
            CaldavItem(
                uid=result.uid,
                calendar_url=result.url,
                title=title,
                item_type=item_type,
                starts_at=starts_at,
                ends_at=starts_at,
                alarm_minutes_before=alarm_minutes_before,
            )
        )
    return f"Created {item_type}: {title} at {starts_at}."


def update_execution_calendar_item(
    *,
    uid: str,
    title: str | None,
    starts_at: datetime | None,
    item_type: str | None,
    duration_minutes: int | None,
    alarm_minutes_before: int | None,
    calendar_name: str | None,
) -> str:
    stored_alarm = stored_alarm_minutes_before(uid)
    result = update_calendar_item(
        uid=uid,
        title=title,
        starts_at=starts_at,
        duration_minutes=duration_minutes,
        item_type=item_type,
        alarm_minutes_before=alarm_minutes_before if alarm_minutes_before is not None else stored_alarm,
        calendar_name=calendar_name,
    )
    try_update_caldav_record(
        uid=uid,
        title=title,
        item_type=item_type,
        starts_at=starts_at,
        duration_minutes=duration_minutes,
        alarm_minutes_before=alarm_minutes_before,
        calendar_url=result.url,
        updated_at=datetime.utcnow(),
    )
    return result.url


def delete_execution_calendar_item(uid: str, calendar_name: str | None = None) -> None:
    delete_calendar_item(uid=uid, calendar_name=calendar_name)
    try_delete_caldav_record(uid)
