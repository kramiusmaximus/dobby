from __future__ import annotations

from dobby_app.entrypoints.api import app, bot, dispatcher, health, lifespan, set_webhook, telegram_webhook

__all__ = [
    "app",
    "bot",
    "dispatcher",
    "health",
    "lifespan",
    "set_webhook",
    "telegram_webhook",
]
