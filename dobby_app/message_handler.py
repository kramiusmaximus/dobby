from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message
from aiogram.types import ReactionTypeEmoji
from sqlalchemy import select

from dobby_app.commands import handle_command, upcoming
from dobby_app.config import settings
from dobby_app.context_templates import load_context_template
from dobby_app.db import session_scope
from dobby_app.memory_agent import answer_memory_query
from dobby_app.models import TelegramMessage
from dobby_app.router import ActionPlan, PlannedAction, assistant_chat, plan_actions
from dobby_app.timeparse import parse_datetime
from dobby_app.transcription import download_voice, transcribe_audio
from dobby_app.wiki_memory import delete_wiki_line, handle_memory_command, save_memory_note, update_wiki_line


logger = logging.getLogger(__name__)
EXECUTOR_CONTEXT = load_context_template("executor.md")


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
    outputs: list[str] = []
    for action in plan.actions:
        try:
            result = await _execute_action(action, text, conversation_context)
        except Exception as exc:
            result = f"I could not complete that: {exc}"
        if result and result.strip():
            outputs.append(result.strip())

    if outputs:
        return "\n\n".join(outputs)
    return await assistant_chat(text, conversation_context)


async def _execute_action(
    action: PlannedAction,
    text: str,
    conversation_context: list[dict[str, str]] | None,
) -> str | None:
    args = action.arguments
    if action.tool == "message":
        return args.get("content") or args.get("query") or args.get("title")

    if action.tool == "calendar":
        operation = action.operation or "read"
        if operation == "read":
            return upcoming(days=int(args.get("days") or 14))
        if operation == "create":
            title = args.get("title") or args.get("query")
            when = args.get("datetime")
            kind = args.get("kind") or "event"
            if not title or not when:
                return _missing_argument_message("Calendar writes require a title and datetime.")
            item_type = "reminder" if kind == "reminder" else "event"
            alarm = args.get("alarm_minutes_before")
            if item_type == "reminder" and alarm is None:
                alarm = 0
            return _create_routed_item(title, when, item_type, alarm)
        return "Calendar update/delete is not implemented yet."

    if action.tool == "wiki":
        operation = action.operation or "read"
        if operation == "read":
            return await answer_memory_query(args.get("query") or text)
        if operation == "create":
            content = args.get("content") or args.get("query") or text
            save_memory_note(content)
            return None
        if operation == "update":
            path = args.get("path")
            exact_line = args.get("exact_line")
            replacement = args.get("replacement")
            if replacement is None:
                replacement = args.get("content")
            if not path or not exact_line or replacement is None:
                return _missing_argument_message(
                    "wiki.update requires a path, exact_line, and replacement."
                )
            return update_wiki_line(
                path=path,
                exact_line=exact_line,
                replacement=replacement,
                reason=action.reason,
            )
        if operation == "delete":
            path = args.get("path")
            exact_line = args.get("exact_line")
            if not path or not exact_line:
                return _missing_argument_message("wiki.delete requires a path and exact_line.")
            return delete_wiki_line(path=path, exact_line=exact_line, reason=action.reason)
        return "Wiki operation is not implemented yet."

    return None


def _missing_argument_message(policy_line: str) -> str:
    if policy_line not in EXECUTOR_CONTEXT:
        logger.warning("Executor policy line is not documented in context template: %s", policy_line)
    if policy_line.startswith("Calendar"):
        return "What should I put on the calendar, and when?"
    if "update" in policy_line:
        return "Which exact wiki line should I update?"
    if "delete" in policy_line:
        return "Which exact wiki line should I delete?"
    return "I need one more detail before I do that."


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
