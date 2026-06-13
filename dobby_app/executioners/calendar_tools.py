from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dobby_app.scheduling.calendar_service import (
    create_execution_calendar_item,
    delete_execution_calendar_item,
    list_calendar_items_and_sync,
    update_execution_calendar_item,
)
from dobby_app.core.config import settings
from dobby_app.assistant.execution_results import ToolExecutionResult, ToolStatus
from dobby_app.executioners.common import schema
from dobby_app.core.timeparse import parse_datetime


def calendar_read_range(
    start: str | None = None,
    end: str | None = None,
    calendar_name: str | None = None,
) -> ToolExecutionResult:
    if start:
        starts_at = parse_datetime(start)
    else:
        starts_at = datetime.now(ZoneInfo(settings.app_timezone))
    ends_at = parse_datetime(end) if end else starts_at + timedelta(days=14)
    items = list_calendar_items_and_sync(starts_at, ends_at, calendar_name=calendar_name)
    message = "Nothing scheduled." if not items else "\n".join(
        f"- {item['summary']} — {item['start']}" for item in items
    )
    return ToolExecutionResult(
        tool="calendar",
        operation="read",
        status=ToolStatus.SUCCESS,
        message=message,
        data={"start": starts_at, "end": ends_at, "calendar_name": calendar_name, "items": items},
    )


def calendar_create(
    title: str | None = None,
    datetime: str | None = None,
    kind: str | None = None,
    duration_minutes: int | None = None,
    alarm_minutes_before: int | None = None,
    calendar_name: str | None = None,
) -> ToolExecutionResult:
    if not title or not datetime:
        return ToolExecutionResult(
            tool="calendar",
            operation="create",
            status=ToolStatus.NEEDS_CLARIFICATION,
            message="What should I put on the calendar, and when?",
        )
    item_type = "reminder" if kind == "reminder" else "event"
    alarm = alarm_minutes_before
    if item_type == "reminder" and alarm is None:
        alarm = 0
    return ToolExecutionResult(
        tool="calendar",
        operation="create",
        status=ToolStatus.SUCCESS,
        message=create_calendar_item_from_text(title, datetime, item_type, alarm, duration_minutes, calendar_name),
        data={
            "title": title,
            "datetime": datetime,
            "kind": item_type,
            "duration_minutes": duration_minutes or 15,
            "calendar_name": calendar_name,
        },
    )


def calendar_update(
    uid: str | None = None,
    title: str | None = None,
    datetime: str | None = None,
    kind: str | None = None,
    duration_minutes: int | None = None,
    alarm_minutes_before: int | None = None,
    calendar_name: str | None = None,
) -> ToolExecutionResult:
    if not uid:
        return ToolExecutionResult(
            tool="calendar",
            operation="update",
            status=ToolStatus.NEEDS_CLARIFICATION,
            message="Which calendar item UID should I update?",
        )
    starts_at = parse_datetime(datetime) if datetime else None
    item_type = "reminder" if kind == "reminder" else "event" if kind == "event" else None
    url = update_execution_calendar_item(
        uid=uid,
        title=title,
        starts_at=starts_at,
        item_type=item_type,
        duration_minutes=duration_minutes,
        alarm_minutes_before=alarm_minutes_before,
        calendar_name=calendar_name,
    )
    return ToolExecutionResult(
        tool="calendar",
        operation="update",
        status=ToolStatus.SUCCESS,
        message=f"Updated calendar item: {uid}.",
        data={"uid": uid, "url": url},
    )


def calendar_delete(uid: str | None = None, calendar_name: str | None = None) -> ToolExecutionResult:
    if not uid:
        return ToolExecutionResult(
            tool="calendar",
            operation="delete",
            status=ToolStatus.NEEDS_CLARIFICATION,
            message="Which calendar item UID should I delete?",
        )
    delete_execution_calendar_item(uid=uid, calendar_name=calendar_name)
    return ToolExecutionResult(
        tool="calendar",
        operation="delete",
        status=ToolStatus.SUCCESS,
        message=f"Deleted calendar item: {uid}.",
        data={"uid": uid},
    )


def create_calendar_item_from_text(
    title: str,
    when: str,
    item_type: str,
    alarm_minutes_before: int | None,
    duration_minutes: int | None,
    calendar_name: str | None,
) -> str:
    starts_at = parse_datetime(when)
    return create_execution_calendar_item(
        title=title,
        starts_at=starts_at,
        item_type=item_type,
        alarm_minutes_before=alarm_minutes_before,
        duration_minutes=duration_minutes,
        calendar_name=calendar_name,
    )


def calendar_read_schema() -> dict:
    return schema(
        "calendar_read_range",
        (
            "Read calendar-backed events/reminders in an explicit time range. `start` and `end` are natural-language "
            "or ISO-like datetimes parsed in DOBBY's configured timezone. If `start` is null, the range starts now. "
            "If `end` is null, the range ends 14 days after start. `calendar_name` optionally restricts the read to "
            "one CalDAV calendar; null uses DOBBY's configured default calendar."
        ),
        {
            "start": {"type": ["string", "null"]},
            "end": {"type": ["string", "null"]},
            "calendar_name": {"type": ["string", "null"]},
        },
        ["start", "end", "calendar_name"],
    )


def calendar_create_schema() -> dict:
    return schema(
        "calendar_create_item",
        (
            "Create one calendar-backed event or reminder. `title` is the visible calendar summary. `datetime` is a "
            "natural-language or ISO-like start datetime. `kind` must be `reminder` for notifications/alerts or "
            "`event` for appointments/meetings/plans. `duration_minutes` controls event length and defaults to 15 "
            "when null. `alarm_minutes_before` controls DISPLAY alarm timing; reminders default to 0 when null. "
            "`calendar_name` optionally selects a CalDAV calendar; null uses DOBBY's configured calendar."
        ),
        {
            "title": {"type": ["string", "null"]},
            "datetime": {"type": ["string", "null"]},
            "kind": {"type": ["string", "null"], "enum": ["reminder", "event", None]},
            "duration_minutes": {"type": ["integer", "null"]},
            "alarm_minutes_before": {"type": ["integer", "null"]},
            "calendar_name": {"type": ["string", "null"]},
        },
        ["title", "datetime", "kind", "duration_minutes", "alarm_minutes_before", "calendar_name"],
    )


def calendar_update_schema() -> dict:
    return schema(
        "calendar_update_item",
        (
            "Update one existing calendar item by CalDAV UID. First read a range if the UID is not known. Pass null "
            "for fields that should remain unchanged. `datetime` changes the start time. `duration_minutes` changes "
            "the end time relative to the start. `kind` changes DOBBY category metadata. `alarm_minutes_before` "
            "sets DISPLAY alarm timing when provided. `calendar_name` optionally selects the CalDAV calendar to "
            "search; null uses DOBBY's configured calendar."
        ),
        {
            "uid": {"type": ["string", "null"]},
            "title": {"type": ["string", "null"]},
            "datetime": {"type": ["string", "null"]},
            "kind": {"type": ["string", "null"], "enum": ["reminder", "event", None]},
            "duration_minutes": {"type": ["integer", "null"]},
            "alarm_minutes_before": {"type": ["integer", "null"]},
            "calendar_name": {"type": ["string", "null"]},
        },
        ["uid", "title", "datetime", "kind", "duration_minutes", "alarm_minutes_before", "calendar_name"],
    )


def calendar_delete_schema() -> dict:
    return schema(
        "calendar_delete_item",
        (
            "Delete one existing calendar item by CalDAV UID. First read a range if the UID is not known. "
            "`calendar_name` optionally selects the CalDAV calendar to search; null uses DOBBY's configured calendar."
        ),
        {
            "uid": {"type": ["string", "null"]},
            "calendar_name": {"type": ["string", "null"]},
        },
        ["uid", "calendar_name"],
    )
