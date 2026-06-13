from __future__ import annotations

from typing import Any

from dobby_app.assistant.execution_results import ToolExecutionResult, ToolStatus
from dobby_app.assistant.tools.common import schema
from dobby_app.db.session import session_scope
from dobby_app.services.jobs import (
    create_job,
    delete_job,
    enqueue_named_job,
    find_job,
    list_jobs_text,
    lookup_job,
    show_job_text,
    update_job,
)


def jobs_list_schema() -> dict:
    return schema("jobs_list", "List scheduled jobs.", {}, [])


def jobs_show_schema() -> dict:
    return schema("jobs_show", "Show one scheduled job.", {"name": {"type": "string"}}, ["name"])


def jobs_create_schema() -> dict:
    return schema(
        "jobs_create",
        "Create a scheduled planner-prompt job.",
        {
            "name": {"type": "string"},
            "schedule": {"type": "string"},
            "prompt": {"type": "string"},
            "display_name": {"type": ["string", "null"]},
            "enabled": {"type": ["boolean", "null"]},
        },
        ["name", "schedule", "prompt", "display_name", "enabled"],
    )


def jobs_update_schema() -> dict:
    return schema(
        "jobs_update",
        "Update a scheduled planner-prompt job.",
        {
            "current_name": {"type": "string"},
            "name": {"type": ["string", "null"]},
            "schedule": {"type": ["string", "null"]},
            "prompt": {"type": ["string", "null"]},
            "display_name": {"type": ["string", "null"]},
            "enabled": {"type": ["boolean", "null"]},
        },
        ["current_name", "name", "schedule", "prompt", "display_name", "enabled"],
    )


def jobs_delete_schema() -> dict:
    return schema("jobs_delete", "Delete one exact scheduled job.", {"name": {"type": "string"}}, ["name"])


def jobs_run_schema() -> dict:
    return schema("jobs_run", "Enqueue one scheduled job now.", {"name": {"type": "string"}}, ["name"])


def jobs_pause_schema() -> dict:
    return schema("jobs_pause", "Pause one scheduled job.", {"name": {"type": "string"}}, ["name"])


def jobs_resume_schema() -> dict:
    return schema("jobs_resume", "Resume one scheduled job.", {"name": {"type": "string"}}, ["name"])


def jobs_list() -> ToolExecutionResult:
    with session_scope() as session:
        return _success("read", list_jobs_text(session))


def jobs_show(name: str) -> ToolExecutionResult:
    with session_scope() as session:
        return _success("read", show_job_text(find_job(session, name)))


def jobs_create(
    name: str,
    schedule: str,
    prompt: str,
    display_name: str | None = None,
    enabled: bool | None = None,
) -> ToolExecutionResult:
    with session_scope() as session:
        job = create_job(
            session,
            name=name,
            schedule_text=schedule,
            prompt=prompt,
            display_name=display_name,
            enabled=True if enabled is None else enabled,
        )
        return _success("create", f"Created {job.display_name}.")


def jobs_update(
    current_name: str,
    name: str | None = None,
    schedule: str | None = None,
    prompt: str | None = None,
    display_name: str | None = None,
    enabled: bool | None = None,
) -> ToolExecutionResult:
    if all(value is None for value in (name, schedule, prompt, display_name, enabled)):
        return _clarification("update", "What should I change on that job?")
    with session_scope() as session:
        job = update_job(
            session,
            find_job(session, current_name),
            name=name,
            schedule_text=schedule,
            prompt=prompt,
            display_name=display_name,
            enabled=enabled,
        )
        return _success("update", f"Updated {job.display_name}.")


def jobs_delete(name: str) -> ToolExecutionResult:
    with session_scope() as session:
        lookup = lookup_job(session, name, exact=True)
        if not lookup.job:
            fuzzy = lookup_job(session, name)
            if fuzzy.matches:
                names = ", ".join(job.name for job in fuzzy.matches[:8])
                return _clarification("delete", f"Which exact job should I delete? Matches: {names}")
            return _clarification("delete", f"I could not find a job named {name}.")
        return _success("delete", delete_job(session, name))


def jobs_run(name: str) -> ToolExecutionResult:
    with session_scope() as session:
        job = find_job(session, name)
        run = enqueue_named_job(session, name)
        return _success("run", f"Queued {job.display_name} as run #{run.id}.")


def jobs_pause(name: str) -> ToolExecutionResult:
    with session_scope() as session:
        job = update_job(session, find_job(session, name), enabled=False)
        return _success("pause", f"Paused {job.display_name}.")


def jobs_resume(name: str) -> ToolExecutionResult:
    with session_scope() as session:
        job = update_job(session, find_job(session, name), enabled=True)
        return _success("resume", f"Resumed {job.display_name}.")


def _success(operation: str, message: str, data: dict[str, Any] | None = None) -> ToolExecutionResult:
    return ToolExecutionResult(
        tool="jobs",
        operation=operation,
        status=ToolStatus.SUCCESS,
        message=message,
        data=data or {},
    )


def _clarification(operation: str, message: str) -> ToolExecutionResult:
    return ToolExecutionResult(
        tool="jobs",
        operation=operation,
        status=ToolStatus.NEEDS_CLARIFICATION,
        message=message,
    )
