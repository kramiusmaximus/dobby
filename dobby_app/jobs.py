from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from dobby_app.caldav_client import list_items
from dobby_app.config import settings
from dobby_app.db import SessionLocal
from dobby_app.models import JobRun, ScheduledJob
from dobby_app.telegram_client import send_telegram_message


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
    upcoming = list_items(now, now + timedelta(days=14))
    lines = [
        "Daily DOBBY briefing",
        "",
        "What do you plan to accomplish today?",
    ]
    if upcoming:
        lines.extend(["", "Upcoming:"])
        for item in upcoming[:10]:
            lines.append(f"- {item['summary']} — {item['start']}")
    await send_telegram_message("\n".join(lines))
    return {"sent": True, "upcoming_count": len(upcoming)}


async def _wiki_maintenance() -> dict:
    await send_telegram_message(
        "Wiki maintenance job is queued. Automated linting is scaffolded; full wiki editing should run through DOBBY's maintenance worker."
    )
    return {"sent": True}


async def _telegram_reconciliation() -> dict:
    await send_telegram_message("Telegram reconciliation checked in. Webhook handling is the primary intake path.")
    return {"sent": True}


def enqueue_job(session: Session, job: ScheduledJob) -> JobRun:
    from dobby_app.queueing import default_queue

    run = JobRun(scheduled_job_id=job.id, status="queued")
    session.add(run)
    session.flush()
    rq_job = default_queue().enqueue(run_scheduled_job, job.id, run.id)
    run.rq_job_id = rq_job.id
    return run
