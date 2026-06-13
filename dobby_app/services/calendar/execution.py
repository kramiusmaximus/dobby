from __future__ import annotations

from datetime import datetime

from dobby_app.db.models import CaldavItem
from dobby_app.db.repositories.calendar_items import (
    stored_alarm_minutes_before,
    try_delete_caldav_record,
    try_update_caldav_record,
)
from dobby_app.db.session import session_scope
from dobby_app.integrations.caldav import create_calendar_item, delete_calendar_item, update_calendar_item


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
