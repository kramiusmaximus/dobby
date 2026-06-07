from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message
from aiogram.types import ReactionTypeEmoji

from dobby_app.commands import handle_command, upcoming
from dobby_app.db import session_scope
from dobby_app.models import TelegramMessage
from dobby_app.router import assistant_chat, route_message
from dobby_app.timeparse import parse_datetime
from dobby_app.transcription import download_voice, transcribe_audio


logger = logging.getLogger(__name__)


async def handle_message(message: Message, bot: Bot) -> str | None:
    text = message.text or message.caption or ""
    if message.voice:
        voice_path = await download_voice(message, bot)
        text = await transcribe_audio(voice_path)

    with session_scope() as session:
        session.add(
            TelegramMessage(
                update_id=None,
                message_id=message.message_id,
                chat_id=message.chat.id,
                sender_id=message.from_user.id if message.from_user else 0,
                text=text,
                kind="voice" if message.voice else "text",
                raw=message.model_dump(mode="json"),
            )
        )

        if text.startswith("/"):
            return handle_command(session, text, sender_id=message.from_user.id if message.from_user else None)

    if not text.strip():
        return None
    return await handle_plain_text(text)


async def handle_plain_text(text: str) -> str:
    routed = await route_message(text)
    if routed.action == "clarify" or routed.confidence < 0.45:
        return routed.clarification or "I need one more detail before I do that."

    args = routed.arguments
    try:
        if routed.action == "create_calendar_reminder":
            title = args.get("title") or args.get("query")
            when = args.get("datetime")
            if not title or not when:
                return "What should I remind you about, and when?"
            return _create_routed_item(title, when, "reminder", args.get("alarm_minutes_before", 0))

        if routed.action == "create_calendar_event":
            title = args.get("title") or args.get("query")
            when = args.get("datetime")
            if not title or not when:
                return "What event should I create, and when?"
            return _create_routed_item(title, when, "event", args.get("alarm_minutes_before"))

        if routed.action == "list_upcoming":
            return upcoming(days=14)

        if routed.action in {"chat", "wiki_query", "daily_briefing"}:
            return await assistant_chat(text)
    except Exception as exc:
        return f"I could not complete that: {exc}"

    return await assistant_chat(text)


def _create_routed_item(
    title: str,
    when: str,
    item_type: str,
    alarm_minutes_before: int | None,
) -> str:
    from dobby_app.caldav_client import create_calendar_item
    from dobby_app.models import CaldavItem

    starts_at = parse_datetime(when)
    with session_scope() as session:
        result = create_calendar_item(
            title=title,
            starts_at=starts_at,
            item_type=item_type,
            alarm_minutes_before=alarm_minutes_before,
        )
        session.add(
            CaldavItem(
                uid=result.uid,
                calendar_url=result.url,
                title=title,
                item_type=item_type,
                starts_at=starts_at,
                ends_at=starts_at,
                alarm_minutes_before=alarm_minutes_before,
            )
        )
    return f"Created {item_type}: {title} at {starts_at}."


async def reply_to_message(bot: Bot, message: Message) -> None:
    try:
        response = await handle_message(message, bot)
    except Exception as exc:
        logger.exception("Telegram message handling failed")
        await bot.send_message(
            message.chat.id,
            _failure_message(exc),
            disable_web_page_preview=True,
            reply_to_message_id=message.message_id,
        )
        return

    if response and response.strip():
        await bot.send_message(
            message.chat.id,
            response,
            disable_web_page_preview=True,
            reply_to_message_id=message.message_id,
        )
        return

    await acknowledge_message(bot, message)


async def acknowledge_message(bot: Bot, message: Message) -> None:
    try:
        await bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=[ReactionTypeEmoji(emoji="👍")],
        )
    except TelegramAPIError:
        logger.exception("Could not set Telegram reaction; falling back to message acknowledgement")
        await bot.send_message(message.chat.id, "👍", reply_to_message_id=message.message_id)


def _failure_message(exc: Exception) -> str:
    return f"Request failed: {type(exc).__name__}\nContext: {exc}"
