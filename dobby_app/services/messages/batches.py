from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from uuid import uuid4

from aiogram import Bot
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from dobby_app.assistant.planner_runner import execute_action_plan_task_results
from dobby_app.assistant.router import plan_actions
from dobby_app.config.settings import settings
from dobby_app.db.models import TelegramMessage
from dobby_app.db.session import session_scope
from dobby_app.services.messages.history import context_content, recent_conversation_context, record_assistant_sent_message

logger = logging.getLogger(__name__)


def process_due_message_batches_sync() -> int:
    if not settings.telegram_bot_token:
        logger.info("Skipping Telegram batch processing; TELEGRAM_BOT_TOKEN is not configured")
        return 0
    return asyncio.run(process_due_message_batches())


async def process_due_message_batches(bot: Bot | None = None) -> int:
    owns_bot = bot is None
    bot = bot or Bot(token=settings.telegram_bot_token)
    try:
        processed = 0
        while True:
            batch = claim_next_due_batch()
            if not batch:
                return processed
            await process_claimed_batch(bot, batch)
            processed += 1
    finally:
        if owns_bot:
            await bot.session.close()


def claim_next_due_batch(now: datetime | None = None) -> list[TelegramMessage] | None:
    now = now or datetime.utcnow()
    debounce_cutoff = now - timedelta(seconds=settings.telegram_batch_debounce_seconds)
    stale_cutoff = now - timedelta(seconds=settings.telegram_batch_stale_processing_seconds)
    batch_id = uuid4().hex

    with session_scope() as session:
        chat_ids = (
            session.execute(
                select(TelegramMessage.chat_id)
                .where(
                    TelegramMessage.text.is_not(None),
                    TelegramMessage.text != "",
                    TelegramMessage.kind != "assistant",
                    TelegramMessage.planner_processed_at.is_(None),
                    or_(
                        TelegramMessage.planner_processing_started_at.is_(None),
                        TelegramMessage.planner_processing_started_at < stale_cutoff,
                    ),
                )
                .group_by(TelegramMessage.chat_id)
                .order_by(TelegramMessage.chat_id)
            )
            .scalars()
            .all()
        )
        for chat_id in chat_ids:
            rows = _eligible_unprocessed_messages(session, chat_id, stale_cutoff)
            if not rows:
                continue
            newest = max(row.created_at for row in rows)
            if newest > debounce_cutoff:
                continue
            for row in rows:
                row.planner_batch_id = batch_id
                row.planner_processing_started_at = now
            session.flush()
            for row in rows:
                session.expunge(row)
            return rows
    return None


async def process_claimed_batch(bot: Bot, rows: list[TelegramMessage]) -> None:
    if not rows:
        return
    chat_id = rows[0].chat_id
    latest_text = "\n\n".join((row.text or "").strip() for row in rows if (row.text or "").strip())
    conversation_context = batch_conversation_context(rows)
    plan = await plan_actions(latest_text, conversation_context)
    task_responses = await execute_action_plan_task_results(plan, latest_text, conversation_context)
    fallback_message_id = rows[-1].message_id
    valid_message_ids = {row.message_id for row in rows}

    for response in task_responses:
        if not response.text:
            continue
        target_message_id = next(
            (message_id for message_id in response.source_message_ids if message_id in valid_message_ids),
            fallback_message_id,
        )
        sent_message = await bot.send_message(
            chat_id,
            response.text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_to_message_id=target_message_id,
        )
        with session_scope() as session:
            record_assistant_sent_message(session, chat_id, sent_message, response.text)

    mark_batch_processed(rows)


def batch_conversation_context(rows: list[TelegramMessage]) -> list[dict[str, str]]:
    if not rows:
        return []
    with session_scope() as session:
        prior_context = recent_conversation_context(
            session,
            rows[0].chat_id,
            before_id=rows[0].id,
            processed_only=True,
        )
    return [
        *prior_context,
        {"role": "user", "content": format_new_messages_for_planner(rows)},
    ]


def format_new_messages_for_planner(rows: list[TelegramMessage]) -> str:
    lines = [
        "New Telegram messages to process as one batch.",
        "Decide whether this batch contains 1, 2, or N distinct tasks.",
        "",
    ]
    for row in rows:
        content = context_content(row, (row.text or "").strip())
        lines.extend(
            [
                f"message_id={row.message_id}",
                f"created_at={row.created_at.isoformat()}",
                f"kind={row.kind}",
                content,
                "",
            ]
        )
    return "\n".join(lines).strip()


def mark_batch_processed(rows: list[TelegramMessage], now: datetime | None = None) -> None:
    now = now or datetime.utcnow()
    ids = [row.id for row in rows]
    with session_scope() as session:
        stored_rows = session.scalars(select(TelegramMessage).where(TelegramMessage.id.in_(ids))).all()
        for row in stored_rows:
            row.planner_processed_at = now


def _eligible_unprocessed_messages(
    session: Session,
    chat_id: int,
    stale_cutoff: datetime,
) -> list[TelegramMessage]:
    return (
        session.execute(
            select(TelegramMessage)
            .where(
                TelegramMessage.chat_id == chat_id,
                TelegramMessage.text.is_not(None),
                TelegramMessage.text != "",
                TelegramMessage.kind != "assistant",
                TelegramMessage.planner_processed_at.is_(None),
                or_(
                    TelegramMessage.planner_processing_started_at.is_(None),
                    TelegramMessage.planner_processing_started_at < stale_cutoff,
                ),
            )
            .order_by(TelegramMessage.id)
        )
        .scalars()
        .all()
    )
