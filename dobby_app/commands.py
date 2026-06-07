from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import desc
from sqlalchemy.orm import Session

from dobby_app.caldav_client import create_calendar_item, list_items
from dobby_app.config import settings
from dobby_app.jobs import enqueue_job
from dobby_app.models import CaldavItem, JobRun, ScheduledJob
from dobby_app.schedules import parse_schedule
from dobby_app.timeparse import parse_datetime


def handle_command(session: Session, text: str) -> str:
    parts = text.strip().split(maxsplit=2)
    command = parts[0].lower()
    rest = text[len(parts[0]) :].strip()

    if command == "/jobs":
        return list_jobs(session)
    if command == "/queue":
        return queue_status(session)
    if command == "/today":
        return upcoming(days=1)
    if command == "/upcoming":
        return upcoming(days=14)
    if command == "/remind":
        return create_from_text(session, rest, item_type="reminder")
    if command == "/event":
        return create_from_text(session, rest, item_type="event")
    if command == "/job":
        return handle_job_command(session, rest)
    return "Unknown command."


def list_jobs(session: Session) -> str:
    jobs = session.query(ScheduledJob).order_by(ScheduledJob.name).all()
    if not jobs:
        return "No jobs configured."
    lines = ["Jobs:"]
    for job in jobs:
        status = "active" if job.enabled else "paused"
        lines.append(f"- {job.name}: {status}, {job.schedule_text}, next {job.next_run_at or 'pending'}")
    return "\n".join(lines)


def queue_status(session: Session) -> str:
    runs = session.query(JobRun).order_by(desc(JobRun.id)).limit(10).all()
    if not runs:
        return "Queue is empty."
    lines = ["Recent queue runs:"]
    for run in runs:
        lines.append(f"- #{run.id}: {run.status}" + (f" — {run.error}" if run.error else ""))
    return "\n".join(lines)


def handle_job_command(session: Session, rest: str) -> str:
    action, _, remainder = rest.partition(" ")
    action = action.lower()

    if action == "show":
        job = _find_job(session, remainder)
        return (
            f"{job.display_name}\n"
            f"name: {job.name}\n"
            f"status: {'active' if job.enabled else 'paused'}\n"
            f"schedule: {job.schedule_text}\n"
            f"type: {job.job_type}\n"
            f"last run: {job.last_run_at or 'never'}\n"
            f"next run: {job.next_run_at or 'pending'}"
        )
    if action == "run":
        job = _find_job(session, remainder)
        run = enqueue_job(session, job)
        return f"Queued {job.display_name} as run #{run.id}."
    if action in {"pause", "resume"}:
        job = _find_job(session, remainder)
        job.enabled = action == "resume"
        job.updated_at = datetime.utcnow()
        return f"{'Resumed' if job.enabled else 'Paused'} {job.display_name}."
    if action == "schedule":
        name, _, schedule_text = remainder.partition(" ")
        job = _find_job(session, name)
        parsed = parse_schedule(schedule_text)
        job.schedule_text = parsed.schedule_text
        job.cron = parsed.cron
        job.updated_at = datetime.utcnow()
        return f"Updated {job.display_name} schedule to: {job.schedule_text}."
    if action == "retry":
        run = session.get(JobRun, int(remainder.strip()))
        if not run or not run.scheduled_job_id:
            return "Could not find a retryable job run."
        job = session.get(ScheduledJob, run.scheduled_job_id)
        if not job:
            return "Could not find the original scheduled job."
        new_run = enqueue_job(session, job)
        return f"Retried {job.display_name} as run #{new_run.id}."

    return "Use /job show|run|pause|resume|schedule|retry."


def create_from_text(session: Session, text: str, item_type: str) -> str:
    title, starts_at = _split_title_datetime(text)
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
    )
    session.add(item)
    return f"Created {item_type}: {title} at {starts_at}."


def upcoming(days: int) -> str:
    tz = ZoneInfo(settings.app_timezone)
    now = datetime.now(tz)
    items = list_items(now, now + timedelta(days=days))
    if not items:
        return "Nothing scheduled."
    return "\n".join(f"- {item['summary']} — {item['start']}" for item in items)


def _find_job(session: Session, name: str) -> ScheduledJob:
    needle = name.strip()
    job = session.query(ScheduledJob).filter_by(name=needle).one_or_none()
    if not job:
        job = session.query(ScheduledJob).filter(ScheduledJob.name.like(f"%{needle}%")).first()
    if not job:
        raise ValueError(f"Job not found: {needle}")
    return job


def _split_title_datetime(text: str) -> tuple[str, datetime]:
    if " at " in text:
        title, when = text.rsplit(" at ", 1)
    elif " tomorrow " in text.lower():
        title, when = text, "tomorrow 09:00"
    else:
        raise ValueError("Use a title and time, for example: /remind Call dentist at tomorrow 9")
    return title.strip(), parse_datetime(when.strip())
