from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from dobby_app.db.repositories.jobs import find_scheduled_job, list_scheduled_jobs, recent_job_runs
from dobby_app.services.jobs import enqueue_job
from dobby_app.db.models import JobRun, ScheduledJob
from dobby_app.utils.schedules import parse_schedule


def list_jobs(session: Session) -> str:
    jobs = list_scheduled_jobs(session)
    if not jobs:
        return "No jobs configured."
    lines = ["Jobs:"]
    for job in jobs:
        status = "active" if job.enabled else "paused"
        lines.append(f"- {job.name}: {status}, {job.schedule_text}, next {job.next_run_at or 'pending'}")
    return "\n".join(lines)


def queue_status(session: Session) -> str:
    runs = recent_job_runs(session)
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
        job = find_job(session, remainder)
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
        job = find_job(session, remainder)
        run = enqueue_job(session, job)
        return f"Queued {job.display_name} as run #{run.id}."
    if action in {"pause", "resume"}:
        job = find_job(session, remainder)
        job.enabled = action == "resume"
        job.updated_at = datetime.utcnow()
        return f"{'Resumed' if job.enabled else 'Paused'} {job.display_name}."
    if action == "schedule":
        name, _, schedule_text = remainder.partition(" ")
        job = find_job(session, name)
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


def find_job(session: Session, name: str) -> ScheduledJob:
    return find_scheduled_job(session, name)
