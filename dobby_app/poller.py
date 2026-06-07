from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.types import Update

from dobby_app.config import settings
from dobby_app.db import init_db, session_scope
from dobby_app.message_handler import reply_to_message
from dobby_app.seed import seed_default_jobs


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def poll_forever() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    init_db()
    with session_scope() as session:
        seed_default_jobs(session)

    bot = Bot(token=settings.telegram_bot_token)
    offset: int | None = None

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        logger.info("Telegram webhook disabled; polling every %s seconds", settings.telegram_poll_interval_seconds)

        while True:
            try:
                updates = await bot.get_updates(
                    offset=offset,
                    timeout=10,
                    allowed_updates=["message", "edited_message"],
                )
                for update in updates:
                    offset = update.update_id + 1
                    await handle_update(bot, update)
            except Exception:
                logger.exception("Telegram polling cycle failed")

            await asyncio.sleep(settings.telegram_poll_interval_seconds)
    finally:
        await bot.session.close()


async def handle_update(bot: Bot, update: Update) -> None:
    message = update.message or update.edited_message
    if not message:
        return
    if settings.telegram_user_id and message.from_user and message.from_user.id != settings.telegram_user_id:
        logger.info("Ignoring Telegram message from unauthorized user %s", message.from_user.id)
        return
    await reply_to_message(bot, message)


def main() -> None:
    asyncio.run(poll_forever())


if __name__ == "__main__":
    main()
