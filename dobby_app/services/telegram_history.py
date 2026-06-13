from __future__ import annotations

from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.orm import Session

from dobby_app.config.settings import settings
from dobby_app.db.session import session_scope
from dobby_app.db.models import TelegramMessage


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
