from __future__ import annotations

import re
from dataclasses import dataclass

from apscheduler.triggers.cron import CronTrigger


@dataclass(frozen=True)
class ParsedSchedule:
    schedule_text: str
    cron: dict[str, str | int]


def parse_schedule(text: str) -> ParsedSchedule:
    raw = text.strip()
    lowered = raw.lower()

    every_hours = re.fullmatch(r"every\s+(\d+)\s+hours?", lowered)
    if every_hours:
        return ParsedSchedule(raw, {"hour": f"*/{int(every_hours.group(1))}", "minute": 0})

    daily = re.fullmatch(r"(every day|daily)\s+at\s+(\d{1,2})(?::(\d{2}))?", lowered)
    if daily:
        hour = int(daily.group(2))
        minute = int(daily.group(3) or 0)
        return ParsedSchedule(raw, {"hour": hour, "minute": minute})

    weekly = re.fullmatch(
        r"(mondays?|tuesdays?|wednesdays?|thursdays?|fridays?|saturdays?|sundays?)\s+at\s+(\d{1,2})(?::(\d{2}))?",
        lowered,
    )
    if weekly:
        day = weekly.group(1)[:3]
        hour = int(weekly.group(2))
        minute = int(weekly.group(3) or 0)
        return ParsedSchedule(raw, {"day_of_week": day, "hour": hour, "minute": minute})

    if lowered.startswith("rrule:"):
        return rrule_to_cron(raw)
    if lowered.startswith("freq="):
        return rrule_to_cron(raw)

    raise ValueError(
        "Unsupported schedule. Use examples like 'every day at 8:30', 'Sundays at 11', or 'every 2 hours'."
    )


def rrule_to_cron(text: str) -> ParsedSchedule:
    body = text.removeprefix("RRULE:").removeprefix("rrule:")
    parts = {}
    for chunk in body.split(";"):
        if "=" in chunk:
            key, value = chunk.split("=", 1)
            parts[key.upper()] = value

    cron: dict[str, str | int] = {}
    if "BYHOUR" in parts:
        cron["hour"] = int(parts["BYHOUR"].split(",")[0])
    if "BYMINUTE" in parts:
        cron["minute"] = int(parts["BYMINUTE"].split(",")[0])
    if "BYDAY" in parts:
        cron["day_of_week"] = ",".join(day[:2].lower() for day in parts["BYDAY"].split(","))
    if parts.get("FREQ") == "DAILY":
        cron.setdefault("hour", 0)
        cron.setdefault("minute", 0)
    if parts.get("FREQ") == "WEEKLY":
        cron.setdefault("day_of_week", "*")
        cron.setdefault("hour", 0)
        cron.setdefault("minute", 0)
    if not cron:
        raise ValueError(f"Unsupported RRULE schedule: {text}")
    return ParsedSchedule(text, cron)


def cron_trigger(cron: dict, timezone: str) -> CronTrigger:
    return CronTrigger(timezone=timezone, **cron)
