from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

from dobby_app.message_handler import (
    _is_daily_plan_reply,
    _message_already_recorded,
    _recent_conversation_context,
    _save_daily_plan_response,
    handle_memory_agent_command,
    handle_plain_text,
)
from dobby_app.models import TelegramMessage
from dobby_app.router import RoutedAction


def test_daily_plan_reply_is_detected():
    message = SimpleNamespace(
        reply_to_message=SimpleNamespace(text="Today\n\nWhat do you plan to accomplish today?", caption=None)
    )

    assert _is_daily_plan_reply(message)


def test_daily_plan_response_saves_memory(monkeypatch):
    saved = []

    monkeypatch.setattr("dobby_app.message_handler.save_memory_note", saved.append)

    response = _save_daily_plan_response("Finish the DOBBY briefing update")

    assert response == "Saved today's plan to Obsidian."
    assert saved == ["Daily plan: Finish the DOBBY briefing update"]


def test_message_already_recorded_detects_duplicate(monkeypatch, sqlite_session):
    @contextmanager
    def fake_session_scope():
        yield sqlite_session
        sqlite_session.commit()

    monkeypatch.setattr("dobby_app.message_handler.session_scope", fake_session_scope)
    message = SimpleNamespace(message_id=1988, chat=SimpleNamespace(id=1106380883))

    assert not _message_already_recorded(message)

    sqlite_session.add(
        TelegramMessage(
            update_id=None,
            message_id=1988,
            chat_id=1106380883,
            sender_id=1106380883,
            text="/upcoming",
            kind="text",
            raw={},
        )
    )
    sqlite_session.commit()

    assert _message_already_recorded(message)


def test_memory_command_routes_query_to_agent(monkeypatch):
    calls = []

    async def fake_answer_memory_query(query):
        calls.append(query)
        return "Agent answer"

    monkeypatch.setattr("dobby_app.message_handler.answer_memory_query", fake_answer_memory_query)

    response = asyncio.run(handle_memory_agent_command("/memory TouchDesigner"))

    assert response == "Agent answer"
    assert calls == ["TouchDesigner"]


def test_plain_wiki_query_routes_to_agent(monkeypatch):
    async def fake_route_message(text, conversation_context=None):
        return RoutedAction(
            action="wiki_query",
            arguments={"query": "Narjiss"},
            confidence=0.9,
        )

    calls = []

    async def fake_answer_memory_query(query):
        calls.append(query)
        return "Wiki answer"

    monkeypatch.setattr("dobby_app.message_handler.route_message", fake_route_message)
    monkeypatch.setattr("dobby_app.message_handler.answer_memory_query", fake_answer_memory_query)

    response = asyncio.run(handle_plain_text("What do you remember about Narjiss?"))

    assert response == "Wiki answer"
    assert calls == ["Narjiss"]


def test_recent_conversation_context_uses_latest_messages_in_order(monkeypatch, sqlite_session):
    monkeypatch.setattr("dobby_app.message_handler.settings.telegram_context_message_count", 3)
    for index in range(5):
        sqlite_session.add(
            TelegramMessage(
                update_id=None,
                message_id=100 + index,
                chat_id=1106380883,
                sender_id=1106380883,
                text=f"user {index}",
                kind="text",
                raw={},
            )
        )
    sqlite_session.add(
        TelegramMessage(
            update_id=None,
            message_id=200,
            chat_id=1106380883,
            sender_id=0,
            text="assistant reply",
            kind="assistant",
            raw={},
        )
    )
    sqlite_session.commit()

    context = _recent_conversation_context(sqlite_session, 1106380883)

    assert context == [
        {"role": "user", "content": "user 3"},
        {"role": "user", "content": "user 4"},
        {"role": "assistant", "content": "assistant reply"},
    ]


def test_plain_text_passes_conversation_context_to_router_and_chat(monkeypatch):
    context = [{"role": "user", "content": "Earlier context"}]
    calls = []

    async def fake_route_message(text, conversation_context=None):
        calls.append(("route", text, conversation_context))
        return RoutedAction(action="chat", arguments={}, confidence=0.9)

    async def fake_assistant_chat(text, conversation_context=None):
        calls.append(("chat", text, conversation_context))
        return "Assistant answer"

    monkeypatch.setattr("dobby_app.message_handler.route_message", fake_route_message)
    monkeypatch.setattr("dobby_app.message_handler.assistant_chat", fake_assistant_chat)

    response = asyncio.run(handle_plain_text("Latest message", context))

    assert response == "Assistant answer"
    assert calls == [
        ("route", "Latest message", context),
        ("chat", "Latest message", context),
    ]
