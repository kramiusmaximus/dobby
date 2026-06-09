from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message
from aiogram.types import ReactionTypeEmoji
from sqlalchemy import select

from dobby_app.commands import handle_command, upcoming
from dobby_app.config import settings
from dobby_app.db import session_scope
from dobby_app.memory_agent import answer_memory_query
from dobby_app.models import TelegramMessage
from dobby_app.router import assistant_chat, route_message
from dobby_app.timeparse import parse_datetime
from dobby_app.transcription import download_voice, transcribe_audio
from dobby_app.wiki_memory import handle_memory_command, save_memory_note


logger = logging.getLogger(__name__)
DAILY_PLAN_PROMPT = "What do you plan to accomplish today?"


async def handle_message(message: Message, bot: Bot) -> str | None:
    if _message_already_recorded(message):
        logger.info("Skipping duplicate Telegram message %s in chat %s", message.message_id, message.chat.id)
        return None

    text = message.text or message.caption or ""
    if message.voice:
        voice_path = await download_voice(message, bot)
        text = await transcribe_audio(voice_path)

    conversation_context = None
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
        session.flush()

        if text.startswith("/"):
            command = text.strip().split(maxsplit=1)[0].lower()
            if command == "/memory":
                return await handle_memory_agent_command(text)
            return handle_command(session, text)

        conversation_context = _recent_conversation_context(session, message.chat.id)

    if _is_daily_plan_reply(message):
        return _save_daily_plan_response(text)

    if not text.strip():
        return None
    return await handle_plain_text(text, conversation_context)


def _message_already_recorded(message: Message) -> bool:
    with session_scope() as session:
        return (
            session.scalar(
                select(TelegramMessage.id).where(
                    TelegramMessage.message_id == message.message_id,
                    TelegramMessage.chat_id == message.chat.id,
                )
            )
            is not None
        )


def _recent_conversation_context(session, chat_id: int) -> list[dict[str, str]]:
    limit = max(settings.telegram_context_message_count, 1)
    rows = (
        session.execute(
            select(TelegramMessage)
            .where(TelegramMessage.chat_id == chat_id, TelegramMessage.text.is_not(None))
            .order_by(TelegramMessage.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    messages: list[dict[str, str]] = []
    for row in reversed(rows):
        content = (row.text or "").strip()
        if not content:
            continue
        role = "assistant" if row.kind == "assistant" else "user"
        messages.append({"role": role, "content": content})
    return messages


def _record_assistant_message(message: Message, sent_message: Message, text: str) -> None:
    with session_scope() as session:
        session.add(
            TelegramMessage(
                update_id=None,
                message_id=sent_message.message_id,
                chat_id=message.chat.id,
                sender_id=sent_message.from_user.id if sent_message.from_user else 0,
                text=text,
                kind="assistant",
                raw=sent_message.model_dump(mode="json"),
            )
        )


async def handle_plain_text(text: str, conversation_context: list[dict[str, str]] | None = None) -> str:
    routed = await route_message(text, conversation_context)
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

        if routed.action == "wiki_query":
            query = args.get("query") or text
            return await answer_memory_query(query)

        if routed.action in {"chat", "daily_briefing"}:
            return await assistant_chat(text, conversation_context)
    except Exception as exc:
        return f"I could not complete that: {exc}"

    return await assistant_chat(text, conversation_context)


async def handle_memory_agent_command(text: str) -> str:
    rest = text[len("/memory") :].strip()
    action, _, _remainder = rest.partition(" ")
    if not rest or action.lower() in {"save", "remember"}:
        return handle_memory_command(rest)

    return await answer_memory_query(rest)


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


def _is_daily_plan_reply(message: Message) -> bool:
    reply = message.reply_to_message
    if not reply:
        return False
    prompt_text = reply.text or reply.caption or ""
    return DAILY_PLAN_PROMPT in prompt_text


def _save_daily_plan_response(text: str) -> str | None:
    plan = text.strip()
    if not plan:
        return None
    save_memory_note(f"Daily plan: {plan}")
    return "Saved today's plan to Obsidian."


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
        sent_message = await bot.send_message(
            message.chat.id,
            response,
            disable_web_page_preview=True,
            reply_to_message_id=message.message_id,
        )
        _record_assistant_message(message, sent_message, response)
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
