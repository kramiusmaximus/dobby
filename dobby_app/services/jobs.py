from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from dobby_app.db.models import JobRun, ScheduledJob
from dobby_app.db.repositories.jobs import list_scheduled_jobs, recent_job_runs
from dobby_app.utils.schedules import parse_schedule


PLANNER_PROMPT_JOB_TYPE = "planner_prompt"

DEFAULT_JOB_PROMPTS = {
    "daily-telegram-message": (
        "Prepare and send Mark's daily briefing for today. Use available calendar, reminder, memory, "
        "and message tools. Include today's calendar/reminder items, important upcoming context from memory, "
        "and a concise prompt asking what Mark plans to accomplish today."
    ),
    "dobby-memory-maintenance": (
        "Review DOBBY memory for obvious stale structure, missing filing, and useful maintenance actions. "
        "Make safe memory updates when the target is exact, then send Mark a concise summary."
    ),
}

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,127}$")


@dataclass(frozen=True)
class JobLookup:
    job: ScheduledJob | None
    matches: list[ScheduledJob]


def list_jobs_text(session: Session) -> str:
    jobs = list_scheduled_jobs(session)
    if not jobs:
        return "No jobs configured."
    lines = ["Jobs:"]
    for job in jobs:
        status = "active" if job.enabled else "paused"
        lines.append(f"- {job.name}: {status}, {job.schedule_text}, next {job.next_run_at or 'pending'}")
    return "\n".join(lines)


def queue_status_text(session: Session) -> str:
    runs = recent_job_runs(session)
    if not runs:
        return "Queue is empty."
    lines = ["Recent queue runs:"]
    for run in runs:
        lines.append(f"- #{run.id}: {run.status}" + (f" — {run.error}" if run.error else ""))
    return "\n".join(lines)


def show_job_text(job: ScheduledJob) -> str:
    return (
        f"{job.display_name}\n"
        f"name: {job.name}\n"
        f"status: {'active' if job.enabled else 'paused'}\n"
        f"schedule: {job.schedule_text}\n"
        f"type: {job.job_type}\n"
        f"prompt: {_preview(job.prompt)}\n"
        f"last run: {job.last_run_at or 'never'}\n"
        f"next run: {job.next_run_at or 'pending'}"
    )


def find_job(session: Session, name: str, *, exact: bool = False) -> ScheduledJob:
    lookup = lookup_job(session, name, exact=exact)
    if lookup.job:
        return lookup.job
    if lookup.matches:
        names = ", ".join(job.name for job in lookup.matches[:8])
        raise ValueError(f"Job name is ambiguous. Be more specific: {names}")
    raise ValueError(f"Job not found: {name.strip()}")


def lookup_job(session: Session, name: str, *, exact: bool = False) -> JobLookup:
    needle = name.strip()
    if not needle:
        return JobLookup(job=None, matches=[])
    exact_job = session.query(ScheduledJob).filter_by(name=needle).one_or_none()
    if exact_job or exact:
        return JobLookup(job=exact_job, matches=[exact_job] if exact_job else [])
    matches = (
        session.query(ScheduledJob)
        .filter(ScheduledJob.name.like(f"%{needle}%"))
        .order_by(ScheduledJob.name)
        .limit(10)
        .all()
    )
    if len(matches) == 1:
        return JobLookup(job=matches[0], matches=matches)
    return JobLookup(job=None, matches=matches)


def create_job(
    session: Session,
    *,
    name: str,
    schedule_text: str,
    prompt: str,
    display_name: str | None = None,
    enabled: bool = True,
) -> ScheduledJob:
    name = normalize_job_name(name)
    prompt = _require_text(prompt, "prompt")
    parsed = parse_schedule(_require_text(schedule_text, "schedule"))
    if session.query(ScheduledJob).filter_by(name=name).one_or_none():
        raise ValueError(f"Job already exists: {name}")
    job = ScheduledJob(
        name=name,
        display_name=display_name.strip() if display_name and display_name.strip() else name,
        enabled=enabled,
        schedule_text=parsed.schedule_text,
        cron=parsed.cron,
        prompt=prompt,
        job_type=PLANNER_PROMPT_JOB_TYPE,
        updated_at=datetime.utcnow(),
    )
    session.add(job)
    session.flush()
    return job


def update_job(
    session: Session,
    job: ScheduledJob,
    *,
    name: str | None = None,
    schedule_text: str | None = None,
    prompt: str | None = None,
    display_name: str | None = None,
    enabled: bool | None = None,
) -> ScheduledJob:
    if name is not None:
        new_name = normalize_job_name(name)
        existing = session.query(ScheduledJob).filter_by(name=new_name).one_or_none()
        if existing and existing.id != job.id:
            raise ValueError(f"Job already exists: {new_name}")
        job.name = new_name
    if display_name is not None:
        job.display_name = display_name.strip() or job.name
    if schedule_text is not None:
        parsed = parse_schedule(_require_text(schedule_text, "schedule"))
        job.schedule_text = parsed.schedule_text
        job.cron = parsed.cron
        job.next_run_at = None
    if prompt is not None:
        job.prompt = _require_text(prompt, "prompt")
    if enabled is not None:
        job.enabled = enabled
    job.job_type = PLANNER_PROMPT_JOB_TYPE
    job.updated_at = datetime.utcnow()
    session.flush()
    return job


def delete_job(session: Session, name: str) -> str:
    lookup = lookup_job(session, name, exact=True)
    if lookup.job:
        display_name = lookup.job.display_name
        session.delete(lookup.job)
        session.flush()
        return f"Deleted {display_name}."
    fuzzy = lookup_job(session, name)
    if fuzzy.matches:
        names = ", ".join(job.name for job in fuzzy.matches[:8])
        return f"Job name is ambiguous. Use an exact name: {names}"
    return f"Job not found: {name.strip()}"


def enqueue_named_job(session: Session, name: str) -> JobRun:
    from dobby_app.workflows.jobs import enqueue_job

    return enqueue_job(session, find_job(session, name))


def retry_job_run(session: Session, run_id: int) -> tuple[ScheduledJob, JobRun] | None:
    from dobby_app.workflows.jobs import enqueue_job

    run = session.get(JobRun, run_id)
    if not run or not run.scheduled_job_id:
        return None
    job = session.get(ScheduledJob, run.scheduled_job_id)
    if not job:
        return None
    return job, enqueue_job(session, job)


def parse_job_fields(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for token in shlex.split(text):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key.strip().lower()] = value.strip()
    if "display" in fields and "display_name" not in fields:
        fields["display_name"] = fields.pop("display")
    if "enabled" in fields:
        fields["enabled"] = parse_bool(fields["enabled"])
    return fields


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "yes", "y", "1", "on", "active", "enabled"}:
        return True
    if normalized in {"false", "no", "n", "0", "off", "paused", "disabled"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value}")


def normalize_job_name(name: str) -> str:
    normalized = _require_text(name, "name").strip().lower()
    if not SLUG_RE.fullmatch(normalized):
        raise ValueError("Job name must be a lowercase slug using letters, numbers, '_' or '-'.")
    return normalized


def planner_prompt_for_seed(name: str, prompt: str | None) -> str:
    if prompt and prompt.strip():
        return prompt.strip()
    return DEFAULT_JOB_PROMPTS.get(name, f"Run the scheduled job named {name} and send Mark a concise result.")


def _require_text(value: str, field: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"Missing required field: {field}")
    return normalized


def _preview(text: str, limit: int = 220) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."
