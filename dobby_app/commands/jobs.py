from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from dobby_app.services.jobs import (
    PLANNER_PROMPT_JOB_TYPE,
    create_job,
    delete_job,
    enqueue_named_job,
    find_job,
    list_jobs_text,
    parse_job_fields,
    queue_status_text,
    retry_job_run,
    show_job_text,
    update_job,
)
from dobby_app.utils.schedules import parse_schedule


def list_jobs(session: Session) -> str:
    return list_jobs_text(session)


def queue_status(session: Session) -> str:
    return queue_status_text(session)


def handle_job_command(session: Session, rest: str) -> str:
    action, _, remainder = rest.partition(" ")
    action = action.lower()

    if not action or action == "list":
        return list_jobs(session)
    if action == "show":
        job = find_job(session, remainder)
        return show_job_text(job)
    if action == "create":
        fields = parse_job_fields(remainder)
        missing = [field for field in ("name", "schedule", "prompt") if not fields.get(field)]
        if missing:
            return (
                f"Missing required job field(s): {', '.join(missing)}.\n"
                'Use: /job create name=<slug> schedule="<schedule>" prompt="<prompt>" '
                '[display="<display name>"] [enabled=true|false]'
            )
        job = create_job(
            session,
            name=fields["name"],
            schedule_text=fields["schedule"],
            prompt=fields["prompt"],
            display_name=fields.get("display_name"),
            enabled=fields.get("enabled", True),
        )
        return f"Created {job.display_name}."
    if action == "update":
        name, _, field_text = remainder.partition(" ")
        if not name.strip():
            return (
                "Missing job name.\n"
                'Use: /job update <name> [name=<new-slug>] [display="<display name>"] '
                '[schedule="<schedule>"] [prompt="<prompt>"] [enabled=true|false]'
            )
        fields = parse_job_fields(field_text)
        if not fields:
            return (
                "Missing fields to update.\n"
                'Use: /job update <name> [name=<new-slug>] [display="<display name>"] '
                '[schedule="<schedule>"] [prompt="<prompt>"] [enabled=true|false]'
            )
        job = update_job(
            session,
            find_job(session, name),
            name=fields.get("name"),
            schedule_text=fields.get("schedule"),
            prompt=fields.get("prompt"),
            display_name=fields.get("display_name"),
            enabled=fields.get("enabled"),
        )
        return f"Updated {job.display_name}."
    if action == "delete":
        if not remainder.strip():
            return "Missing job name. Use: /job delete <exact-name>"
        return delete_job(session, remainder)
    if action == "run":
        job = find_job(session, remainder)
        run = enqueue_named_job(session, remainder)
        return f"Queued {job.display_name} as run #{run.id}."
    if action in {"pause", "resume"}:
        job = find_job(session, remainder)
        job.enabled = action == "resume"
        job.job_type = PLANNER_PROMPT_JOB_TYPE
        job.updated_at = datetime.utcnow()
        return f"{'Resumed' if job.enabled else 'Paused'} {job.display_name}."
    if action == "schedule":
        name, _, schedule_text = remainder.partition(" ")
        job = find_job(session, name)
        parsed = parse_schedule(schedule_text)
        update_job(session, job, schedule_text=parsed.schedule_text)
        return f"Updated {job.display_name} schedule to: {job.schedule_text}."
    if action == "retry":
        retried = retry_job_run(session, int(remainder.strip()))
        if not retried:
            return "Could not find the original scheduled job."
        job, new_run = retried
        return f"Retried {job.display_name} as run #{new_run.id}."

    return "Use /job list|show|create|update|delete|run|pause|resume|schedule|retry."
