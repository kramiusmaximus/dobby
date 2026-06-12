from __future__ import annotations

from datetime import timedelta
import logging

from sqlalchemy.exc import SQLAlchemyError

from dobby_app.db import session_scope
from dobby_app.execution_results import ToolExecutionResult
from dobby_app.executioner_agent import ExecutionTool, run_executioner_agent
from dobby_app.executioners.common import needs_clarification_schema, schema
from dobby_app.models import CaldavItem
from dobby_app.router import ConversationMessage, PlannedAction
from dobby_app.timeparse import parse_datetime


logger = logging.getLogger(__name__)


async def execute_calendar_action(
    action: PlannedAction,
    latest_text: str,
    conversation_context: list[ConversationMessage] | None = None,
) -> ToolExecutionResult:
    operation = action.operation or "read"
    return await run_executioner_agent(
        executor_name="calendar",
        context_template="tools/calendar.md",
        action=action,
        latest_text=latest_text,
        conversation_context=conversation_context,
        tools=[
            ExecutionTool(schema=_calendar_read_schema(), handler=_calendar_read_range, terminal=True),
            ExecutionTool(schema=_calendar_create_schema(), handler=_calendar_create, terminal=True),
            ExecutionTool(schema=_calendar_update_schema(), handler=_calendar_update, terminal=True),
            ExecutionTool(schema=_calendar_delete_schema(), handler=_calendar_delete, terminal=True),
            ExecutionTool(
                schema=needs_clarification_schema(),
                handler=lambda message: ToolExecutionResult(
                    tool="calendar",
                    operation=operation,
                    status="needs_clarification",
                    message=message,
                ),
                terminal=True,
            ),
        ],
    )


def _calendar_read_range(
    start: str | None = None,
    end: str | None = None,
    calendar_name: str | None = None,
) -> ToolExecutionResult:
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    from dobby_app.caldav_client import list_items
    from dobby_app.config import settings
    from dobby_app.wiki_memory import sync_calendar_snapshot_to_wiki

    if start:
        starts_at = parse_datetime(start)
    else:
        from datetime import datetime

        starts_at = datetime.now(ZoneInfo(settings.app_timezone))
    ends_at = parse_datetime(end) if end else starts_at + timedelta(days=14)
    items = list_items(starts_at, ends_at, calendar_name=calendar_name)
    sync_calendar_snapshot_to_wiki(items)
    message = "Nothing scheduled." if not items else "\n".join(
        f"- {item['summary']} — {item['start']}" for item in items
    )
    return ToolExecutionResult(
        tool="calendar",
        operation="read",
        status="success",
        message=message,
        data={"start": starts_at, "end": ends_at, "calendar_name": calendar_name, "items": items},
    )


def _calendar_create(
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
            status="needs_clarification",
            message="What should I put on the calendar, and when?",
        )
    item_type = "reminder" if kind == "reminder" else "event"
    alarm = alarm_minutes_before
    if item_type == "reminder" and alarm is None:
        alarm = 0
    return ToolExecutionResult(
        tool="calendar",
        operation="create",
        status="success",
        message=_create_calendar_item(title, datetime, item_type, alarm, duration_minutes, calendar_name),
        data={
            "title": title,
            "datetime": datetime,
            "kind": item_type,
            "duration_minutes": duration_minutes or 15,
            "calendar_name": calendar_name,
        },
    )


def _calendar_update(
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
            status="needs_clarification",
            message="Which calendar item UID should I update?",
        )
    from datetime import datetime as datetime_type

    from dobby_app.caldav_client import update_calendar_item

    starts_at = parse_datetime(datetime) if datetime else None
    item_type = "reminder" if kind == "reminder" else "event" if kind == "event" else None
    stored_alarm = _stored_alarm_minutes_before(uid)
    result = update_calendar_item(
        uid=uid,
        title=title,
        starts_at=starts_at,
        duration_minutes=duration_minutes,
        item_type=item_type,
        alarm_minutes_before=alarm_minutes_before if alarm_minutes_before is not None else stored_alarm,
        calendar_name=calendar_name,
    )
    _try_update_caldav_record(
        uid=uid,
        title=title,
        item_type=item_type,
        starts_at=starts_at,
        duration_minutes=duration_minutes,
        alarm_minutes_before=alarm_minutes_before,
        calendar_url=result.url,
        updated_at=datetime_type.utcnow(),
    )
    return ToolExecutionResult(
        tool="calendar",
        operation="update",
        status="success",
        message=f"Updated calendar item: {uid}.",
        data={"uid": uid, "url": result.url},
    )


def _calendar_delete(uid: str | None = None, calendar_name: str | None = None) -> ToolExecutionResult:
    if not uid:
        return ToolExecutionResult(
            tool="calendar",
            operation="delete",
            status="needs_clarification",
            message="Which calendar item UID should I delete?",
        )
    from dobby_app.caldav_client import delete_calendar_item

    delete_calendar_item(uid=uid, calendar_name=calendar_name)
    _try_delete_caldav_record(uid)
    return ToolExecutionResult(
        tool="calendar",
        operation="delete",
        status="success",
        message=f"Deleted calendar item: {uid}.",
        data={"uid": uid},
    )


def _stored_alarm_minutes_before(uid: str) -> int | None:
    try:
        with session_scope() as session:
            item = session.query(CaldavItem).filter_by(uid=uid).one_or_none()
            return item.alarm_minutes_before if item else None
    except SQLAlchemyError as exc:
        logger.warning("Could not read local CalDAV record for %s: %s", uid, exc)
        return None


def _try_update_caldav_record(
    *,
    uid: str,
    title: str | None,
    item_type: str | None,
    starts_at,
    duration_minutes: int | None,
    alarm_minutes_before: int | None,
    calendar_url: str,
    updated_at,
) -> None:
    try:
        with session_scope() as session:
            item = session.query(CaldavItem).filter_by(uid=uid).one_or_none()
            if not item:
                return
            if title is not None:
                item.title = title
            if item_type is not None:
                item.item_type = item_type
            if starts_at is not None:
                item.starts_at = starts_at
                item.ends_at = starts_at
            if duration_minutes is not None:
                item.ends_at = (starts_at or item.starts_at) + timedelta(minutes=duration_minutes)
            if alarm_minutes_before is not None:
                item.alarm_minutes_before = alarm_minutes_before
            item.calendar_url = calendar_url
            item.updated_at = updated_at
    except SQLAlchemyError as exc:
        logger.warning("Could not update local CalDAV record for %s: %s", uid, exc)


def _try_delete_caldav_record(uid: str) -> None:
    try:
        with session_scope() as session:
            item = session.query(CaldavItem).filter_by(uid=uid).one_or_none()
            if item:
                session.delete(item)
    except SQLAlchemyError as exc:
        logger.warning("Could not delete local CalDAV record for %s: %s", uid, exc)


def _create_calendar_item(
    title: str,
    when: str,
    item_type: str,
    alarm_minutes_before: int | None,
    duration_minutes: int | None,
    calendar_name: str | None,
) -> str:
    from dobby_app.caldav_client import create_calendar_item

    starts_at = parse_datetime(when)
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


def _calendar_read_schema() -> dict:
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


def _calendar_create_schema() -> dict:
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


def _calendar_update_schema() -> dict:
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


def _calendar_delete_schema() -> dict:
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
