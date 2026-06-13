from __future__ import annotations

from datetime import date, datetime, timedelta
import random
import re
from zoneinfo import ZoneInfo

from dobby_app.integrations.caldav import list_items
from dobby_app.config.settings import settings
from dobby_app.integrations.obsidian import get_obsidian_client, obsidian_is_enabled
from dobby_app.integrations.telegram import send_telegram_message

DAILY_OPENERS = [
    "The secret of getting ahead is getting started. - Mark Twain",
    "A day without laughter is a day wasted. - Charlie Chaplin",
    "The best way out is always through. - Robert Frost",
    "Well begun is half done. - Aristotle",
    "If at first you do not succeed, skydiving is not for you.",
    "I told my calendar a joke. Its days are numbered.",
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "The road to someday leads to a town called nowhere.",
]


async def daily_briefing() -> dict:
    tz = ZoneInfo(settings.app_timezone)
    now = datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today_start + timedelta(days=1)
    upcoming = list_items(today_start, today_start + timedelta(days=14))
    today_items = [item for item in upcoming if is_today_item(item, tomorrow)]
    next_items = [item for item in upcoming if item not in today_items]

    messages = [
        format_opener_message(),
        format_calendar_message(today_items, next_items),
        format_other_reminders_message(),
        "Today\n\nWhat do you plan to accomplish today?",
    ]
    for message in messages:
        await send_telegram_message(message)
    return {"sent": True, "upcoming_count": len(upcoming)}


def format_opener_message() -> str:
    return f"Start\n\n{random.choice(DAILY_OPENERS)}"


def format_calendar_message(today_items: list[dict], upcoming_items: list[dict]) -> str:
    lines = ["Calendar and Reminders", "", "Today"]
    if today_items:
        lines.extend(format_items(today_items))
    else:
        lines.append("- Nothing scheduled.")

    lines.extend(["", "Next 2 Weeks"])
    if upcoming_items:
        lines.extend(format_items(upcoming_items[:20]))
    else:
        lines.append("- Nothing coming up.")
    return "\n".join(lines)


def format_other_reminders_message() -> str:
    reminders = memory_reminders()
    lines = ["Other Important Reminders", ""]
    if reminders:
        lines.extend(f"- {reminder}" for reminder in reminders[:8])
    else:
        lines.append("- No other standing reminders found in DOBBY memory.")
    return "\n".join(lines)


def memory_reminders() -> list[str]:
    if not obsidian_is_enabled():
        return []

    client = get_obsidian_client()
    reminders = []
    for section in ("goals", "projects", "calendar"):
        for path in sorted(listed_markdown_paths(client.list(f"pages/{section}"), f"pages/{section}")):
            reminders.extend(page_reminders(path, client.read(path)))
            if len(reminders) >= 8:
                return reminders[:8]
    return reminders


def listed_markdown_paths(payload: object, prefix: str) -> list[str]:
    if isinstance(payload, dict):
        values = payload.get("files") or payload.get("children") or payload.get("items") or []
    else:
        values = payload

    paths = []
    for item in values if isinstance(values, list) else []:
        if isinstance(item, str):
            path = item
        elif isinstance(item, dict):
            path = str(item.get("path") or item.get("name") or "")
        else:
            continue
        if not path:
            continue
        if "/" not in path:
            path = f"{prefix.rstrip('/')}/{path}"
        if path.endswith(".md"):
            paths.append(path)
    return paths


def page_reminders(path: str, content: str) -> list[str]:
    if "status: active" not in content:
        return []

    title = frontmatter_value(content, "title") or path.rsplit("/", 1)[-1].removesuffix(".md").replace("-", " ").title()
    lines = content.splitlines()
    collected = []
    capture = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            heading = stripped[3:].strip().lower()
            capture = heading in {"goal", "timing", "current list", "time-bound items"}
            continue
        if not capture:
            continue
        item = clean_memory_line(stripped)
        if item:
            collected.append(f"{title}: {item}")
        if len(collected) >= 2:
            break
    return collected


def frontmatter_value(content: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else None


def clean_memory_line(line: str) -> str | None:
    item = re.sub(r"^[-*]\s+", "", line)
    item = re.sub(r"^\d+\.\s+", "", item)
    item = item.strip()
    if not item:
        return None
    if item.startswith("[[") or item.lower().startswith(("see ", "captured from ")):
        return None
    return item


def format_items(items: list[dict]) -> list[str]:
    return [f"- {format_item(item)}" for item in sorted(items, key=sort_key)]


def format_item(item: dict) -> str:
    start = item_start(item)
    if isinstance(start, datetime):
        when = start.strftime("%a %b %-d, %H:%M")
    elif isinstance(start, date):
        when = start.strftime("%a %b %-d, all day")
    else:
        when = "time unknown"
    return f"{when} - {item.get('summary', 'Untitled')}"


def item_start(item: dict) -> datetime | date | None:
    start = item.get("start")
    return start if isinstance(start, (datetime, date)) else None


def is_today_item(item: dict, tomorrow: datetime) -> bool:
    start = item_start(item)
    if isinstance(start, datetime):
        return start < tomorrow
    if isinstance(start, date):
        return start < tomorrow.date()
    return False


def sort_key(item: dict) -> str:
    start = item_start(item)
    if start:
        return start.isoformat()
    return "9999-12-31T23:59:59"
