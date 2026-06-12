from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

from dobby_app.message_handler import (
    _message_already_recorded,
    _recent_conversation_context,
    handle_message,
    handle_memory_query_command,
    handle_plain_text,
)
from dobby_app.execution_results import ToolExecutionResult
from dobby_app.models import TelegramMessage
from dobby_app.router import ActionPlan, PlannedAction


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

    async def fake_execute_tool_action(action, latest_text, conversation_context=None):
        calls.append((action, latest_text, conversation_context))
        return ToolExecutionResult(
            tool="wiki",
            operation="read",
            status="success",
            message="Agent answer",
            data={"query": action.arguments["query"]},
        )

    monkeypatch.setattr("dobby_app.message_handler.execute_tool_action", fake_execute_tool_action)

    response = asyncio.run(handle_memory_query_command("/memory TouchDesigner"))

    assert response == "Agent answer"
    assert calls[0][0].tool == "wiki"
    assert calls[0][0].operation == "read"
    assert calls[0][0].arguments == {"query": "TouchDesigner"}


def test_plain_wiki_query_routes_to_agent(monkeypatch):
    plan_calls = []

    async def fake_plan_actions(text, conversation_context=None, tool_results=None):
        plan_calls.append(tool_results)
        if tool_results:
            return ActionPlan(
                actions=[
                    PlannedAction(
                        tool="message",
                        operation="send",
                        arguments={"content": "Wiki answer"},
                    )
                ],
                confidence=0.9,
            )
        return ActionPlan(
            actions=[
                PlannedAction(tool="wiki", operation="read", arguments={"query": "Narjiss"})
            ],
            confidence=0.9,
        )

    async def fake_execute_tool_action(action, latest_text, conversation_context=None):
        if action.tool == "wiki":
            return ToolExecutionResult(
                tool="wiki",
                operation="read",
                status="success",
                message="Wiki answer",
                data={"query": action.arguments["query"]},
            )
        return ToolExecutionResult(
            tool="message",
            operation="send",
            status="success",
            message=action.arguments["content"],
        )

    monkeypatch.setattr("dobby_app.message_handler.plan_actions", fake_plan_actions)
    monkeypatch.setattr("dobby_app.message_handler.execute_tool_action", fake_execute_tool_action)

    response = asyncio.run(handle_plain_text("What do you remember about Narjiss?"))

    assert response == "Wiki answer"
    assert plan_calls[1][0]["tool"] == "wiki"
    assert plan_calls[1][0]["message"] == "Wiki answer"


def test_plain_wiki_update_executes_safe_line_update(monkeypatch):
    async def fake_plan_actions(text, conversation_context=None, tool_results=None):
        return ActionPlan(
            actions=[
                PlannedAction(
                    tool="wiki",
                    operation="update",
                    reason="Remove duplicate reminder detail.",
                    arguments={
                        "path": "pages/goals/mother-birthday-gift.md",
                        "exact_line": "- Birthday: 2026-07-08.",
                        "replacement": "",
                    },
                ),
                PlannedAction(
                    tool="message",
                    operation="send",
                    arguments={"content": "Removed the duplicate."},
                ),
            ],
            confidence=0.9,
        )

    calls = []

    async def fake_execute_tool_action(action, latest_text, conversation_context=None):
        calls.append(action)
        if action.tool == "wiki":
            return ToolExecutionResult(
                tool="wiki",
                operation="update",
                status="success",
                message="Updated wiki line in pages/goals/mother-birthday-gift.md.",
            )
        return ToolExecutionResult(
            tool="message",
            operation="send",
            status="success",
            message=action.arguments["content"],
        )

    monkeypatch.setattr("dobby_app.message_handler.plan_actions", fake_plan_actions)
    monkeypatch.setattr("dobby_app.message_handler.execute_tool_action", fake_execute_tool_action)

    response = asyncio.run(handle_plain_text("remove one"))

    assert response == "Removed the duplicate."
    assert calls[0].tool == "wiki"
    assert calls[0].arguments["exact_line"] == "- Birthday: 2026-07-08."


def test_plain_wiki_delete_requires_exact_line(monkeypatch):
    async def fake_plan_actions(text, conversation_context=None, tool_results=None):
        if tool_results:
            return ActionPlan(
                actions=[
                    PlannedAction(
                        tool="message",
                        operation="send",
                        arguments={"content": tool_results[-1]["message"]},
                    )
                ],
                confidence=0.9,
            )
        return ActionPlan(
            actions=[
                PlannedAction(
                    tool="wiki",
                    operation="delete",
                    arguments={"path": "pages/goals/mother-birthday-gift.md"},
                )
            ],
            confidence=0.9,
        )

    monkeypatch.setattr("dobby_app.message_handler.plan_actions", fake_plan_actions)

    async def fake_execute_tool_action(action, latest_text, conversation_context=None):
        if action.tool == "message":
            return ToolExecutionResult(
                tool="message",
                operation="send",
                status="success",
                message=action.arguments["content"],
            )
        return ToolExecutionResult(
            tool="wiki",
            operation="delete",
            status="needs_clarification",
            message="Which exact wiki line should I delete?",
        )

    monkeypatch.setattr("dobby_app.message_handler.execute_tool_action", fake_execute_tool_action)

    response = asyncio.run(handle_plain_text("remove one"))

    assert response == "Which exact wiki line should I delete?"


def test_recent_conversation_context_uses_latest_messages_in_order(monkeypatch, sqlite_session):
    monkeypatch.setattr("dobby_app.message_handler.settings.telegram_context_message_count", 2)
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
    sqlite_session.add(
        TelegramMessage(
            update_id=None,
            message_id=201,
            chat_id=1106380883,
            sender_id=1106380883,
            text="remove one",
            kind="text",
            reply_to_message_id=200,
            reply_to_text="Other Important Reminders\n\n- Mother Birthday Gift: Buy present\n- Mother Birthday Gift: Birthday: 2026-07-08",
            reply_to_kind="assistant",
            raw={},
        )
    )
    sqlite_session.commit()

    context = _recent_conversation_context(sqlite_session, 1106380883)

    assert context == [
        {"role": "assistant", "content": "assistant reply"},
        {
            "role": "user",
            "content": (
                "remove one\n\n"
                "[Telegram reply context: this message replies to assistant message_id=200: "
                "Other Important Reminders\n\n"
                "- Mother Birthday Gift: Buy present\n"
                "- Mother Birthday Gift: Birthday: 2026-07-08]"
            ),
        },
    ]


def test_handle_message_stores_reply_metadata_and_passes_context(monkeypatch, sqlite_session):
    @contextmanager
    def fake_session_scope():
        yield sqlite_session
        sqlite_session.commit()

    calls = []

    async def fake_plan_actions(text, conversation_context=None, tool_results=None):
        calls.append((text, conversation_context))
        return ActionPlan(
            actions=[
                PlannedAction(
                    tool="message",
                    operation="send",
                    arguments={"content": "Handled"},
                )
            ],
            confidence=0.9,
        )

    monkeypatch.setattr("dobby_app.message_handler.session_scope", fake_session_scope)
    monkeypatch.setattr("dobby_app.message_handler.plan_actions", fake_plan_actions)
    monkeypatch.setattr("dobby_app.message_handler.settings.telegram_context_message_count", 5)

    async def fake_execute_tool_action(action, latest_text, conversation_context=None):
        return ToolExecutionResult(
            tool="message",
            operation="send",
            status="success",
            message=action.arguments["content"],
        )

    monkeypatch.setattr("dobby_app.message_handler.execute_tool_action", fake_execute_tool_action)

    sqlite_session.add(
        TelegramMessage(
            update_id=None,
            message_id=300,
            chat_id=1106380883,
            sender_id=0,
            text="Other Important Reminders\n\n- Mother Birthday Gift: Buy present",
            kind="assistant",
            raw={},
        )
    )
    sqlite_session.commit()

    message = SimpleNamespace(
        message_id=301,
        text="remove one",
        caption=None,
        voice=None,
        chat=SimpleNamespace(id=1106380883),
        from_user=SimpleNamespace(id=1106380883),
        reply_to_message=SimpleNamespace(
            message_id=300,
            text="Other Important Reminders\n\n- Mother Birthday Gift: Buy present",
            caption=None,
        ),
        model_dump=lambda mode="json": {"message_id": 301},
    )

    response = asyncio.run(handle_message(message, bot=SimpleNamespace()))

    stored = sqlite_session.query(TelegramMessage).filter_by(message_id=301).one()
    assert response == "Handled"
    assert stored.reply_to_message_id == 300
    assert stored.reply_to_kind == "assistant"
    assert stored.reply_to_text == "Other Important Reminders\n\n- Mother Birthday Gift: Buy present"
    assert calls[0][1][-1]["content"].startswith("remove one\n\n[Telegram reply context:")


def test_plain_text_passes_conversation_context_to_router_and_chat(monkeypatch):
    context = [{"role": "user", "content": "Earlier context"}]
    calls = []

    async def fake_plan_actions(text, conversation_context=None, tool_results=None):
        calls.append(("plan", text, conversation_context))
        return ActionPlan(
            actions=[
                PlannedAction(
                    tool="message",
                    operation="send",
                    arguments={"content": "Assistant answer"},
                )
            ],
            confidence=0.9,
        )

    monkeypatch.setattr("dobby_app.message_handler.plan_actions", fake_plan_actions)

    async def fake_execute_tool_action(action, latest_text, conversation_context=None):
        return ToolExecutionResult(
            tool="message",
            operation="send",
            status="success",
            message=action.arguments["content"],
        )

    monkeypatch.setattr("dobby_app.message_handler.execute_tool_action", fake_execute_tool_action)

    response = asyncio.run(handle_plain_text("Latest message", context))

    assert response == "Assistant answer"
    assert calls == [
        ("plan", "Latest message", context),
    ]
