from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, ReactionTypeEmoji

from dobby_app.assistant.planner_runner import (
    execute_action_plan_result,
    handle_plain_text_result,
)
from dobby_app.assistant.router import ActionPlan, PlannedAction
from dobby_app.assistant.tool_dispatch import execute_tool_action
from dobby_app.db.session import session_scope
from dobby_app.integrations.transcription import download_voice, transcribe_audio
from dobby_app.services.memory import handle_memory_command
from dobby_app.services.messages.history import (
    message_already_recorded,
    record_incoming_message,
)

logger = logging.getLogger(__name__)


async def handle_message(message: Message, bot: Bot) -> str | None:
    if message_already_recorded(message):
        logger.info("Skipping duplicate Telegram message %s in chat %s", message.message_id, message.chat.id)
        return None

    text = message.text or message.caption or ""
    if message.voice:
        voice_path = await download_voice(message, bot)
        text = await transcribe_audio(voice_path)

    with session_scope() as session:
        record_incoming_message(session, message, text, kind="voice" if message.voice else "text")
        session.flush()
    return None


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
        if message.voice:
            voice_path = await download_voice(message, bot)
            text = await transcribe_audio(voice_path)
            kind = "voice"
        else:
            kind = "text"
        with session_scope() as session:
            record_incoming_message(session, message, text, kind=kind)
            session.flush()
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
