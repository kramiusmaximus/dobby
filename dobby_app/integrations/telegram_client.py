from __future__ import annotations

from aiogram import Bot

from dobby_app.core.config import settings


def get_bot() -> Bot:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    return Bot(token=settings.telegram_bot_token)


async def send_telegram_message(text: str) -> None:
    if not settings.telegram_user_id:
        raise RuntimeError("TELEGRAM_USER_ID is not configured")
    bot = get_bot()
    try:
        await bot.send_message(
            chat_id=settings.telegram_user_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    finally:
        await bot.session.close()
