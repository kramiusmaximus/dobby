from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message
from aiogram.types import ReactionTypeEmoji
from sqlalchemy import select

from dobby_app.commands import handle_command
from dobby_app.config import settings
from dobby_app.db import session_scope
from dobby_app.memory_agent import answer_memory_query
from dobby_app.models import TelegramMessage
from dobby_app.router import ActionPlan, assistant_chat, plan_actions
from dobby_app.tool_executors import ToolExecutionResult, execute_tool_action
from dobby_app.transcription import download_voice, transcribe_audio
from dobby_app.wiki_memory import handle_memory_command


logger = logging.getLogger(__name__)
MAX_PLANNER_TOOL_ROUNDS = 3


async def handle_message(message: Message, bot: Bot) -> str | None:
    if _message_already_recorded(message):
        logger.info("Skipping duplicate Telegram message %s in chat %s", message.message_id, message.chat.id)
        return None

    text = message.text or message.caption or ""
    if message.voice:
        voice_path = await download_voice(message, bot)
        text = await transcribe_audio(voice_path)

    reply_to_message_id = message.reply_to_message.message_id if message.reply_to_message else None
    reply_to_text = _message_text(message.reply_to_message) if message.reply_to_message else None
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
                reply_to_message_id=reply_to_message_id,
                reply_to_text=reply_to_text,
                reply_to_kind=_reply_kind(session, message.chat.id, reply_to_message_id),
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

    if not text.strip():
        return None
    return await handle_plain_text(text, conversation_context)


def _message_text(message: Message | None) -> str | None:
    if not message:
        return None
    return message.text or message.caption


def _reply_kind(session, chat_id: int, message_id: int | None) -> str | None:
    if message_id is None:
        return None
    return session.scalar(
        select(TelegramMessage.kind).where(
            TelegramMessage.message_id == message_id,
            TelegramMessage.chat_id == chat_id,
        )
    )


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
        messages.append({"role": role, "content": _context_content(row, content)})
    return messages


def _context_content(row: TelegramMessage, content: str) -> str:
    if not row.reply_to_message_id:
        return content
    reply_kind = row.reply_to_kind or "unknown"
    reply_text = (row.reply_to_text or "").strip()
    if reply_text:
        return (
            f"{content}\n\n"
            f"[Telegram reply context: this message replies to {reply_kind} "
            f"message_id={row.reply_to_message_id}: {reply_text}]"
        )
    return f"{content}\n\n[Telegram reply context: this message replies to message_id={row.reply_to_message_id}]"


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
    plan = await plan_actions(text, conversation_context)
    if plan.confidence < 0.35:
        return await assistant_chat(text, conversation_context)
    return await execute_action_plan(plan, text, conversation_context)


async def execute_action_plan(
    plan: ActionPlan,
    text: str,
    conversation_context: list[dict[str, str]] | None = None,
) -> str:
    current_plan = plan
    all_results: list[ToolExecutionResult] = []
    for _round in range(MAX_PLANNER_TOOL_ROUNDS):
        results = await _execute_plan_once(current_plan, text)
        all_results.extend(results)
        message_outputs = [
            result.message
            for result in results
            if result.tool == "message" and result.status == "success" and result.message
        ]
        if message_outputs:
            return "\n\n".join(message_outputs)

        if not _planner_should_continue(results):
            non_message_outputs = [
                result.message for result in results if result.message and result.status != "success"
            ]
            if non_message_outputs:
                return "\n\n".join(non_message_outputs)
            break

        current_plan = await plan_actions(
            text,
            conversation_context,
            tool_results=[_result_payload(result) for result in all_results],
        )

    return await assistant_chat(text, conversation_context)


async def _execute_plan_once(plan: ActionPlan, text: str) -> list[ToolExecutionResult]:
    results = []
    for action in plan.actions:
        try:
            results.append(await execute_tool_action(action, text))
        except Exception as exc:
            results.append(
                ToolExecutionResult(
                    tool=action.tool,
                    operation=action.operation,
                    status="failed",
                    message=f"I could not complete that: {exc}",
                )
            )
    return results


def _planner_should_continue(results: list[ToolExecutionResult]) -> bool:
    if any(result.tool == "message" and result.status == "success" for result in results):
        return False
    return any(result.tool != "message" for result in results)


def _result_payload(result: ToolExecutionResult) -> dict:
    return {
        "tool": result.tool,
        "operation": result.operation,
        "status": result.status,
        "message": result.message,
        "data": result.data,
    }


async def handle_memory_agent_command(text: str) -> str:
    rest = text[len("/memory") :].strip()
    action, _, _remainder = rest.partition(" ")
    if not rest or action.lower() in {"save", "remember"}:
        return handle_memory_command(rest)

    return await answer_memory_query(rest)


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
