from __future__ import annotations

from sqlalchemy.orm import Session

from dobby_app.command_calendar import create_from_text, upcoming
from dobby_app.command_jobs import handle_job_command, list_jobs, queue_status
from dobby_app.config import settings
from dobby_app.runtime_status import current_commit
from dobby_app.wiki_memory import handle_memory_command


def handle_command(session: Session, text: str) -> str:
    parts = text.strip().split(maxsplit=2)
    command = parts[0].lower()
    rest = text[len(parts[0]) :].strip()

    if command == "/status":
        return status()
    if command == "/memory":
        return handle_memory_command(rest)
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


def status() -> str:
    return (
        "DOBBY is running. "
        f"Commit {current_commit()}. "
        f"Telegram intake is polling every {settings.telegram_poll_interval_seconds} seconds."
    )
