from __future__ import annotations

from aiogram import Bot
from aiogram.types import BotCommand


COMMAND_DESCRIPTIONS: tuple[tuple[str, str], ...] = (
    ("help", "Show DOBBY commands."),
    ("commands", "Show DOBBY commands."),
    ("status", "Show DOBBY service status."),
    ("whoami", "Show your Telegram sender id."),
    ("jobs", "List scheduled jobs."),
    ("queue", "Show recent job runs."),
    ("today", "Show calendar items for today."),
    ("upcoming", "Show upcoming calendar items."),
    ("remind", "Create a calendar reminder."),
    ("event", "Create a calendar event."),
    ("job", "Manage a scheduled job."),
)


def command_help_text() -> str:
    lines = [
        "DOBBY commands:",
        "",
        "/today - show calendar items for the next day",
        "/upcoming - show calendar items for the next 14 days",
        "/remind <title> at <time> - create a reminder with an alarm",
        "/event <title> at <time> - create a calendar event",
        "/jobs - list scheduled jobs",
        "/queue - show recent job runs",
        "/job show <name> - show one job config",
        "/job run <name> - queue a job now",
        "/job pause <name> - pause a job",
        "/job resume <name> - resume a job",
        "/job schedule <name> <schedule> - update a job schedule",
        "/job retry <run_id> - retry a previous job run",
        "/status - show service status",
        "/whoami - show your Telegram sender id",
    ]
    return "\n".join(lines)


async def register_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [BotCommand(command=command, description=description) for command, description in COMMAND_DESCRIPTIONS]
    )
