from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import random
import re
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from dobby_app.caldav_client import list_items
from dobby_app.config import settings
from dobby_app.db import SessionLocal
from dobby_app.models import JobRun, ScheduledJob
from dobby_app.obsidian_client import get_obsidian_client, obsidian_is_enabled
from dobby_app.telegram_client import send_telegram_message


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


def run_scheduled_job(job_id: int, job_run_id: int | None = None) -> dict:
    session = SessionLocal()
    try:
        job = session.get(ScheduledJob, job_id)
        if not job:
            raise RuntimeError(f"Scheduled job not found: {job_id}")
        run = session.get(JobRun, job_run_id) if job_run_id else None
        if run:
            run.status = "running"
            run.started_at = datetime.utcnow()
            session.commit()

        result = _execute_job(job)
        job.last_run_at = datetime.utcnow()
        if run:
            run.status = "finished"
            run.finished_at = datetime.utcnow()
            run.result = result
        session.commit()
        return result
    except Exception as exc:
        session.rollback()
        if job_run_id:
            _mark_run_failed(job_run_id, str(exc))
        raise
    finally:
        session.close()


def _mark_run_failed(job_run_id: int, error: str) -> None:
    with SessionLocal() as session:
        run = session.get(JobRun, job_run_id)
        if run:
            run.status = "failed"
            run.finished_at = datetime.utcnow()
            run.error = error
            session.commit()


def _execute_job(job: ScheduledJob) -> dict:
    if job.job_type == "daily_briefing":
        return asyncio.run(_daily_briefing())
    if job.job_type == "wiki_maintenance":
        return asyncio.run(_wiki_maintenance())
    if job.job_type == "telegram_reconciliation":
        return asyncio.run(_telegram_reconciliation())
    return asyncio.run(send_telegram_message(f"Ran job: {job.display_name}")) or {"ok": True}


async def _daily_briefing() -> dict:
    tz = ZoneInfo(settings.app_timezone)
    now = datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today_start + timedelta(days=1)
    upcoming = list_items(today_start, today_start + timedelta(days=14))
    today_items = [item for item in upcoming if _item_start(item) and _item_start(item) < tomorrow]
    next_items = [item for item in upcoming if item not in today_items]

    messages = [
        _format_opener_message(),
        _format_calendar_message(today_items, next_items),
        _format_other_reminders_message(),
        "Today\n\nWhat do you plan to accomplish today?",
    ]
    for message in messages:
        await send_telegram_message(message)
    return {"sent": True, "upcoming_count": len(upcoming)}


def _format_opener_message() -> str:
    return f"Start\n\n{random.choice(DAILY_OPENERS)}"


def _format_calendar_message(today_items: list[dict], upcoming_items: list[dict]) -> str:
    lines = ["Calendar and Reminders", "", "Today"]
    if today_items:
        lines.extend(_format_items(today_items))
    else:
        lines.append("- Nothing scheduled.")

    lines.extend(["", "Next 2 Weeks"])
    if upcoming_items:
        lines.extend(_format_items(upcoming_items[:20]))
    else:
        lines.append("- Nothing coming up.")
    return "\n".join(lines)


def _format_other_reminders_message() -> str:
    reminders = _memory_reminders()
    lines = ["Other Important Reminders", ""]
    if reminders:
        lines.extend(f"- {reminder}" for reminder in reminders[:8])
    else:
        lines.append("- No other standing reminders found in DOBBY memory.")
    return "\n".join(lines)


def _memory_reminders() -> list[str]:
    if not obsidian_is_enabled():
        return []

    client = get_obsidian_client()
    reminders = []
    for section in ("goals", "projects", "calendar"):
        for path in sorted(_listed_markdown_paths(client.list(f"pages/{section}"), f"pages/{section}")):
            reminders.extend(_page_reminders(path, client.read(path)))
            if len(reminders) >= 8:
                return reminders[:8]
    return reminders


def _listed_markdown_paths(payload: object, prefix: str) -> list[str]:
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


def _page_reminders(path: str, content: str) -> list[str]:
    if "status: active" not in content:
        return []

    title = _frontmatter_value(content, "title") or path.rsplit("/", 1)[-1].removesuffix(".md").replace("-", " ").title()
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
        item = _clean_memory_line(stripped)
        if item:
            collected.append(f"{title}: {item}")
        if len(collected) >= 2:
            break
    return collected


def _frontmatter_value(content: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else None


def _clean_memory_line(line: str) -> str | None:
    item = re.sub(r"^[-*]\s+", "", line)
    item = re.sub(r"^\d+\.\s+", "", item)
    item = item.strip()
    if not item:
        return None
    if item.startswith("[[") or item.lower().startswith(("see ", "captured from ")):
        return None
    return item


def _format_items(items: list[dict]) -> list[str]:
    return [f"- {_format_item(item)}" for item in sorted(items, key=_sort_key)]


def _format_item(item: dict) -> str:
    start = _item_start(item)
    when = start.strftime("%a %b %-d, %H:%M") if start else "time unknown"
    return f"{when} - {item.get('summary', 'Untitled')}"


def _item_start(item: dict) -> datetime | None:
    start = item.get("start")
    return start if isinstance(start, datetime) else None


def _sort_key(item: dict) -> str:
    start = _item_start(item)
    if start:
        return start.isoformat()
    return "9999-12-31T23:59:59"


async def _wiki_maintenance() -> dict:
    await send_telegram_message(
        "Wiki maintenance job is queued. Automated linting is scaffolded; full wiki editing should run through DOBBY's maintenance worker."
    )
    return {"sent": True}


async def _telegram_reconciliation() -> dict:
    return {"sent": False, "skipped": True}


def enqueue_job(session: Session, job: ScheduledJob) -> JobRun:
    from dobby_app.queueing import default_queue

    run = JobRun(scheduled_job_id=job.id, status="queued")
    session.add(run)
    session.flush()
    rq_job = default_queue().enqueue(run_scheduled_job, job.id, run.id)
    run.rq_job_id = rq_job.id
    return run
