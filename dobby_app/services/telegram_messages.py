from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message
from aiogram.types import ReactionTypeEmoji
from sqlalchemy import select
from sqlalchemy.orm import Session

from dobby_app.commands import handle_command
from dobby_app.config.settings import settings
from dobby_app.db.models import TelegramMessage
from dobby_app.db.session import session_scope
from dobby_app.assistant.planner_runner import (
    HandlerResponse,
    execute_action_plan_result,
    handle_plain_text_result,
)
from dobby_app.assistant.router import ActionPlan, PlannedAction
from dobby_app.assistant.tool_dispatch import execute_tool_action
from dobby_app.integrations.transcription import download_voice, transcribe_audio
from dobby_app.services.memory import handle_memory_command


logger = logging.getLogger(__name__)


def message_text(message: Message | None) -> str | None:
    if not message:
        return None
    return message.text or message.caption


def message_already_recorded(message: Message) -> bool:
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


def record_incoming_message(session: Session, message: Message, text: str, kind: str) -> None:
    reply_to_message_id = message.reply_to_message.message_id if message.reply_to_message else None
    reply_to_text = message_text(message.reply_to_message) if message.reply_to_message else None
    session.add(
        TelegramMessage(
            update_id=None,
            message_id=message.message_id,
            chat_id=message.chat.id,
            sender_id=message.from_user.id if message.from_user else 0,
            text=text,
            kind=kind,
            reply_to_message_id=reply_to_message_id,
            reply_to_text=reply_to_text,
            reply_to_kind=reply_kind(session, message.chat.id, reply_to_message_id),
            raw=message.model_dump(mode="json"),
        )
    )


def reply_kind(session: Session, chat_id: int, message_id: int | None) -> str | None:
    if message_id is None:
        return None
    return session.scalar(
        select(TelegramMessage.kind).where(
            TelegramMessage.message_id == message_id,
            TelegramMessage.chat_id == chat_id,
        )
    )


def recent_conversation_context(session: Session, chat_id: int) -> list[dict[str, str]]:
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
        messages.append({"role": role, "content": context_content(row, content)})
    return messages


def context_content(row: TelegramMessage, content: str) -> str:
    if not row.reply_to_message_id:
        return content
    reply_kind_value = row.reply_to_kind or "unknown"
    reply_text = (row.reply_to_text or "").strip()
    if reply_text:
        return (
            f"{content}\n\n"
            f"[Telegram reply context: this message replies to {reply_kind_value} "
            f"message_id={row.reply_to_message_id}: {reply_text}]"
        )
    return f"{content}\n\n[Telegram reply context: this message replies to message_id={row.reply_to_message_id}]"


def record_assistant_message(message: Message, sent_message: Message, text: str) -> None:
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


async def handle_message(message: Message, bot: Bot) -> str | None:
    if message_already_recorded(message):
        logger.info("Skipping duplicate Telegram message %s in chat %s", message.message_id, message.chat.id)
        return None

    text = message.text or message.caption or ""
    if message.voice:
        voice_path = await download_voice(message, bot)
        text = await transcribe_audio(voice_path)

    conversation_context = None
    with session_scope() as session:
        record_incoming_message(session, message, text, kind="voice" if message.voice else "text")
        session.flush()

        if text.startswith("/"):
            command = text.strip().split(maxsplit=1)[0].lower()
            if command == "/memory":
                return await handle_memory_query_command(text)
            return handle_command(session, text)

        conversation_context = recent_conversation_context(session, message.chat.id)

    if not text.strip():
        return None
    response = await handle_plain_text_result(text, conversation_context)
    return response.text


async def handle_plain_text(text: str, conversation_context: list[dict[str, str]] | None = None) -> str:
    response = await handle_plain_text_result(text, conversation_context)
    return response.text or response.reaction_emoji or ""


async def execute_action_plan(
    plan: ActionPlan,
    text: str,
    conversation_context: list[dict[str, str]] | None = None,
) -> str:
    response = await execute_action_plan_result(plan, text, conversation_context)
    return response.text or response.reaction_emoji or ""


async def handle_memory_query_command(text: str) -> str:
    rest = text[len("/memory") :].strip()
    action, _, _remainder = rest.partition(" ")
    if not rest or action.lower() in {"save", "remember"}:
        return handle_memory_command(rest)

    result = await execute_tool_action(
        PlannedAction(tool="memory", operation="read", arguments={"query": rest}),
        rest,
        None,
    )
    return result.message or "I searched memory but did not get an answer."


async def reply_to_message(bot: Bot, message: Message) -> None:
    try:
        if message_already_recorded(message):
            logger.info("Skipping duplicate Telegram message %s in chat %s", message.message_id, message.chat.id)
            return

        text = message.text or message.caption or ""
        if text.startswith("/") or message.voice:
            response_text = await handle_message(message, bot)
            response = HandlerResponse(text=response_text)
        else:
            with session_scope() as session:
                record_incoming_message(session, message, text, kind="text")
                session.flush()
                conversation_context = recent_conversation_context(session, message.chat.id)
            response = await handle_plain_text_result(text, conversation_context) if text.strip() else HandlerResponse()
    except Exception as exc:
        logger.exception("Telegram message handling failed")
        await bot.send_message(
            message.chat.id,
            _failure_message(exc),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_to_message_id=message.message_id,
        )
        return

    if response.text and response.text.strip():
        sent_message = await bot.send_message(
            message.chat.id,
            response.text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_to_message_id=message.message_id,
        )
        record_assistant_message(message, sent_message, response.text)
        return

    if response.reaction_emoji:
        await react_to_message(bot, message, response.reaction_emoji)
        return

    await acknowledge_message(bot, message)


async def acknowledge_message(bot: Bot, message: Message) -> None:
    await react_to_message(bot, message, "👍")


async def react_to_message(bot: Bot, message: Message, emoji: str) -> None:
    try:
        await bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=[ReactionTypeEmoji(emoji=emoji)],
        )
    except TelegramAPIError:
        logger.exception("Could not set Telegram reaction; falling back to message acknowledgement")
        await bot.send_message(message.chat.id, emoji, reply_to_message_id=message.message_id)


def _failure_message(exc: Exception) -> str:
    return f"Request failed: {type(exc).__name__}\nContext: {exc}"
