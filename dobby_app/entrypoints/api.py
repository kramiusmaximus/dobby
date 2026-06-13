from __future__ import annotations

from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request

from dobby_app.services.telegram_bot_commands import register_bot_commands
from dobby_app.config.settings import settings
from dobby_app.db.session import init_db, session_scope
from dobby_app.config.logging import configure_logging
from dobby_app.services.telegram_messages import reply_to_message
from dobby_app.utils.runtime_status import runtime_status
from dobby_app.services.job_seed import seed_default_jobs


configure_logging()
bot = Bot(token=settings.telegram_bot_token) if settings.telegram_bot_token else None
dispatcher = Dispatcher()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with session_scope() as session:
        seed_default_jobs(session)
    if bot:
        await register_bot_commands(bot)
    yield


app = FastAPI(title="DOBBY", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return runtime_status("app")


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    if not bot:
        raise HTTPException(status_code=500, detail="Telegram bot token is not configured")

    update = Update.model_validate(await request.json(), context={"bot": bot})
    if update.message:
        await reply_to_message(bot, update.message)
    return {"ok": True}


@app.post("/telegram/set-webhook")
async def set_webhook() -> dict:
    if not bot:
        raise HTTPException(status_code=500, detail="Telegram bot token is not configured")
    if not settings.public_webhook_base_url:
        raise HTTPException(status_code=400, detail="PUBLIC_WEBHOOK_BASE_URL is not configured")
    url = f"{settings.public_webhook_base_url.rstrip('/')}/telegram/webhook"
    await bot.set_webhook(url, secret_token=settings.telegram_webhook_secret or None)
    return {"ok": True, "url": url}
