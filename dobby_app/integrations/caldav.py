from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

import caldav
from icalendar import Alarm, Calendar, Event

from dobby_app.config.settings import settings


@dataclass(frozen=True)
class CalendarWriteResult:
    uid: str
    url: str


def _principal():
    client = caldav.DAVClient(
        url=settings.ical_caldav_url,
        username=settings.ical_caldav_username,
        password=settings.ical_caldav_password,
    )
    return client.principal()


def _calendar(name: str | None = None):
    calendars = _principal().calendars()
    preferred = name or settings.ical_calendar_name or settings.ical_reminder_calendar_name
    if preferred:
        for calendar in calendars:
            if calendar.name == preferred:
                return calendar
        available = ", ".join(calendar.name for calendar in calendars) or "<none>"
        raise RuntimeError(f"CalDAV calendar not found: {preferred}. Available calendars: {available}")
    if not calendars:
        raise RuntimeError("No CalDAV calendars found")
    return calendars[0]


def create_calendar_item(
    *,
    title: str,
    starts_at: datetime,
    duration_minutes: int = 15,
    item_type: str = "event",
    alarm_minutes_before: int | None = 0,
    calendar_name: str | None = None,
) -> CalendarWriteResult:
    uid = f"{uuid4()}@dobby"
    cal = Calendar()
    cal.add("prodid", "-//DOBBY//VPS Assistant//EN")
    cal.add("version", "2.0")

    event = Event()
    event.add("uid", uid)
    event.add("summary", title)
    event.add("dtstart", starts_at)
    event.add("dtend", starts_at + timedelta(minutes=duration_minutes))
    event.add("dtstamp", datetime.utcnow())
    event.add("categories", [f"DOBBY-{item_type.upper()}"])

    if alarm_minutes_before is not None:
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", title)
        alarm.add("trigger", timedelta(minutes=-alarm_minutes_before))
        event.add_component(alarm)

    cal.add_component(event)
    target_calendar = calendar_name
    if target_calendar is None and item_type == "reminder":
        target_calendar = settings.ical_reminder_calendar_name or settings.ical_calendar_name
    calendar = _calendar(target_calendar)
    created = calendar.save_event(cal.to_ical().decode("utf-8"))

    verified = calendar.event_by_uid(uid)
    if not verified:
        raise RuntimeError(f"CalDAV write verification failed for {uid}")
    return CalendarWriteResult(uid=uid, url=str(created.url))


def update_calendar_item(
    *,
    uid: str,
    title: str | None = None,
    starts_at: datetime | None = None,
    duration_minutes: int | None = None,
    item_type: str | None = None,
    alarm_minutes_before: int | None = None,
    calendar_name: str | None = None,
) -> CalendarWriteResult:
    calendar = _calendar(calendar_name)
    existing = calendar.event_by_uid(uid)
    if not existing:
        raise RuntimeError(f"CalDAV item not found: {uid}")

    vevent = existing.vobject_instance.vevent
    current_start = starts_at or vevent.dtstart.value
    current_end = getattr(vevent, "dtend", None)
    if duration_minutes is None and current_end is not None:
        duration = current_end.value - vevent.dtstart.value
    else:
        duration = timedelta(minutes=duration_minutes or 15)

    updated_title = title if title is not None else str(vevent.summary.value)
    updated_type = item_type or _item_type_from_categories(vevent)
    alarm = alarm_minutes_before

    cal = _calendar_payload(
        uid=uid,
        title=updated_title,
        starts_at=current_start,
        duration_minutes=int(duration.total_seconds() // 60),
        item_type=updated_type,
        alarm_minutes_before=alarm,
    )
    existing.data = cal.to_ical().decode("utf-8")
    saved = existing.save()
    return CalendarWriteResult(uid=uid, url=str(getattr(saved, "url", existing.url)))


def delete_calendar_item(*, uid: str, calendar_name: str | None = None) -> str:
    calendar = _calendar(calendar_name)
    existing = calendar.event_by_uid(uid)
    if not existing:
        raise RuntimeError(f"CalDAV item not found: {uid}")
    existing.delete()
    return uid


def list_items(start: datetime, end: datetime, calendar_name: str | None = None) -> list[dict]:
    calendar = _calendar(calendar_name)
    events = calendar.date_search(start=start, end=end, expand=True)
    results = []
    for event in events:
        vevent = event.vobject_instance.vevent
        results.append(
            {
                "uid": str(vevent.uid.value),
                "summary": str(vevent.summary.value),
                "start": vevent.dtstart.value,
                "end": vevent.dtend.value if hasattr(vevent, "dtend") else None,
                "url": str(event.url),
            }
        )
    return results


def _calendar_payload(
    *,
    uid: str,
    title: str,
    starts_at: datetime,
    duration_minutes: int,
    item_type: str,
    alarm_minutes_before: int | None,
) -> Calendar:
    cal = Calendar()
    cal.add("prodid", "-//DOBBY//VPS Assistant//EN")
    cal.add("version", "2.0")

    event = Event()
    event.add("uid", uid)
    event.add("summary", title)
    event.add("dtstart", starts_at)
    event.add("dtend", starts_at + timedelta(minutes=duration_minutes))
    event.add("dtstamp", datetime.utcnow())
    event.add("categories", [f"DOBBY-{item_type.upper()}"])

    if alarm_minutes_before is not None:
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", title)
        alarm.add("trigger", timedelta(minutes=-alarm_minutes_before))
        event.add_component(alarm)

    cal.add_component(event)
    return cal


def _item_type_from_categories(vevent) -> str:
    categories = getattr(vevent, "categories", None)
    if not categories:
        return "event"
    values = getattr(categories, "value", []) or []
    for value in values:
        text = str(value)
        if text.startswith("DOBBY-"):
            return text.removeprefix("DOBBY-").lower()
    return "event"
