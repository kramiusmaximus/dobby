from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from dobby_app.commands.calendar import create_from_text, upcoming
from dobby_app.commands.jobs import handle_job_command, list_jobs, queue_status
from dobby_app.config.settings import settings
from dobby_app.utils.runtime_status import current_commit
from dobby_app.services.memory import handle_memory_command

CommandHandler = Callable[[Session, str], str]


COMMAND_HANDLERS: dict[str, CommandHandler] = {
    "/status": lambda session, rest: status(),
    "/memory": lambda session, rest: handle_memory_command(rest),
    "/jobs": lambda session, rest: list_jobs(session),
    "/queue": lambda session, rest: queue_status(session),
    "/today": lambda session, rest: upcoming(days=1),
    "/upcoming": lambda session, rest: upcoming(days=14),
    "/remind": lambda session, rest: create_from_text(session, rest, item_type="reminder"),
    "/event": lambda session, rest: create_from_text(session, rest, item_type="event"),
    "/job": lambda session, rest: handle_job_command(session, rest),
}


def handle_command(session: Session, text: str) -> str:
    parts = text.strip().split(maxsplit=2)
    command = parts[0].lower()
    rest = text[len(parts[0]) :].strip()
    handler = COMMAND_HANDLERS.get(command)
    return handler(session, rest) if handler else "Unknown command."


def status() -> str:
    return (
        "DOBBY is running. "
        f"Commit {current_commit()}. "
        f"Telegram intake is polling every {settings.telegram_poll_interval_seconds} seconds."
    )
