from __future__ import annotations

from aiogram import Bot
from aiogram.types import BotCommand


COMMAND_DESCRIPTIONS: tuple[tuple[str, str], ...] = (
    ("status", "Show DOBBY service status."),
    ("memory", "Query or update saved memory."),
    ("jobs", "List scheduled jobs."),
    ("queue", "Show recent job runs."),
    ("today", "Show calendar items for today."),
    ("upcoming", "Show upcoming calendar items."),
    ("remind", "Create a calendar reminder."),
    ("event", "Create a calendar event."),
    ("job", "Manage a scheduled job."),
)


async def register_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [BotCommand(command=command, description=description) for command, description in COMMAND_DESCRIPTIONS]
    )
