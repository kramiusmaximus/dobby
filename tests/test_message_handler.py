from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace

from dobby_app.services.messages import (
    batch_conversation_context,
    claim_next_due_batch,
    handle_message,
    handle_memory_query_command,
    handle_plain_text,
)
from dobby_app.assistant.execution_results import ToolExecutionResult
from dobby_app.assistant.tool_dispatch import execute_tool_action
from dobby_app.db.models import TelegramMessage
from dobby_app.assistant.router import ActionPlan, PlannedAction, PlannedTask
from dobby_app.services.messages import message_already_recorded, recent_conversation_context
from dobby_app.services.messages.batches import process_claimed_batch


def test_message_already_recorded_detects_duplicate(monkeypatch, sqlite_session):
    @contextmanager
    def fake_session_scope():
        yield sqlite_session
        sqlite_session.commit()

    monkeypatch.setattr("dobby_app.services.messages.history.session_scope", fake_session_scope)
    message = SimpleNamespace(message_id=1988, chat=SimpleNamespace(id=1106380883))

    assert not message_already_recorded(message)

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

    assert message_already_recorded(message)


def test_memory_command_routes_query_to_agent(monkeypatch):
    calls = []

    async def fake_execute_tool_action(action, latest_text, conversation_context=None):
        calls.append((action, latest_text, conversation_context))
        return ToolExecutionResult(
            tool="memory",
            operation="read",
            status="success",
            message="Agent answer",
            data={"query": action.arguments["query"]},
        )

    monkeypatch.setattr("dobby_app.services.messages.handlers.execute_tool_action", fake_execute_tool_action)

    response = asyncio.run(handle_memory_query_command("/memory TouchDesigner"))

    assert response == "Agent answer"
    assert calls[0][0].tool == "memory"
    assert calls[0][0].operation == "read"
    assert calls[0][0].arguments == {"query": "TouchDesigner"}


def test_plain_memory_query_routes_to_agent(monkeypatch):
    plan_calls = []

    async def fake_plan_actions(text, conversation_context=None, tool_results=None):
        plan_calls.append(tool_results)
        if tool_results:
            return ActionPlan(
                actions=[
                    PlannedAction(
                        tool="message",
                        operation="send",
                        arguments={"content": "Memory answer"},
                    )
                ],
                confidence=0.9,
            )
        return ActionPlan(
            actions=[
                PlannedAction(tool="memory", operation="read", arguments={"query": "Narjiss"})
            ],
            confidence=0.9,
        )

    async def fake_execute_tool_action(action, latest_text, conversation_context=None):
        if action.tool == "memory":
            return ToolExecutionResult(
                tool="memory",
                operation="read",
                status="success",
                message="Memory answer",
                data={"query": action.arguments["query"]},
            )
        return ToolExecutionResult(
            tool="message",
            operation="send",
            status="success",
            message=action.arguments["content"],
        )

    monkeypatch.setattr("dobby_app.assistant.planner_runner.plan_actions", fake_plan_actions)
    monkeypatch.setattr("dobby_app.assistant.planner_runner.execute_tool_action", fake_execute_tool_action)

    response = asyncio.run(handle_plain_text("What do you remember about Narjiss?"))

    assert response == "Memory answer"
    assert plan_calls[1][0]["tool"] == "memory"
    assert plan_calls[1][0]["message"] == "Memory answer"


def test_plain_memory_update_executes_safe_line_update(monkeypatch):
    async def fake_plan_actions(text, conversation_context=None, tool_results=None):
        return ActionPlan(
            actions=[
                PlannedAction(
                    tool="memory",
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
        if action.tool == "memory":
            return ToolExecutionResult(
                tool="memory",
                operation="update",
                status="success",
                message="Updated memory line in pages/goals/mother-birthday-gift.md.",
            )
        return ToolExecutionResult(
            tool="message",
            operation="send",
            status="success",
            message=action.arguments["content"],
        )

    monkeypatch.setattr("dobby_app.assistant.planner_runner.plan_actions", fake_plan_actions)
    monkeypatch.setattr("dobby_app.assistant.planner_runner.execute_tool_action", fake_execute_tool_action)

    response = asyncio.run(handle_plain_text("remove one"))

    assert response == "Removed the duplicate."
    assert calls[0].tool == "memory"
    assert calls[0].arguments["exact_line"] == "- Birthday: 2026-07-08."


def test_plain_memory_delete_requires_exact_line(monkeypatch):
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
                    tool="memory",
                    operation="delete",
                    arguments={"path": "pages/goals/mother-birthday-gift.md"},
                )
            ],
            confidence=0.9,
        )

    monkeypatch.setattr("dobby_app.assistant.planner_runner.plan_actions", fake_plan_actions)

    async def fake_execute_tool_action(action, latest_text, conversation_context=None):
        if action.tool == "message":
            return ToolExecutionResult(
                tool="message",
                operation="send",
                status="success",
                message=action.arguments["content"],
            )
        return ToolExecutionResult(
            tool="memory",
            operation="delete",
            status="needs_clarification",
            message="Which exact memory line should I delete?",
        )

    monkeypatch.setattr("dobby_app.assistant.planner_runner.execute_tool_action", fake_execute_tool_action)

    response = asyncio.run(handle_plain_text("remove one"))

    assert response == "Which exact memory line should I delete?"


def test_recent_conversation_context_uses_latest_messages_in_order(monkeypatch, sqlite_session):
    monkeypatch.setattr("dobby_app.services.messages.history.settings.telegram_context_message_count", 2)
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

    context = recent_conversation_context(sqlite_session, 1106380883)

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


def test_handle_message_stores_reply_metadata_without_planning(monkeypatch, sqlite_session):
    @contextmanager
    def fake_session_scope():
        yield sqlite_session
        sqlite_session.commit()

    monkeypatch.setattr("dobby_app.services.messages.handlers.session_scope", fake_session_scope)
    monkeypatch.setattr("dobby_app.services.messages.history.session_scope", fake_session_scope)
    monkeypatch.setattr("dobby_app.services.messages.history.settings.telegram_context_message_count", 5)

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
    assert response is None
    assert stored.reply_to_message_id == 300
    assert stored.reply_to_kind == "assistant"
    assert stored.reply_to_text == "Other Important Reminders\n\n- Mother Birthday Gift: Buy present"
    assert stored.planner_processed_at is None


def test_claim_next_due_batch_waits_for_debounce(monkeypatch, sqlite_session):
    @contextmanager
    def fake_session_scope():
        yield sqlite_session
        sqlite_session.commit()

    monkeypatch.setattr("dobby_app.services.messages.batches.session_scope", fake_session_scope)
    monkeypatch.setattr("dobby_app.services.messages.batches.settings.telegram_batch_debounce_seconds", 30)
    monkeypatch.setattr("dobby_app.services.messages.batches.settings.telegram_batch_stale_processing_seconds", 300)
    now = datetime(2026, 6, 13, 12, 0, 0)
    sqlite_session.add(
        TelegramMessage(
            update_id=None,
            message_id=401,
            chat_id=1,
            sender_id=1,
            text="too new",
            kind="text",
            created_at=now - timedelta(seconds=10),
            raw={},
        )
    )
    sqlite_session.commit()

    assert claim_next_due_batch(now=now) is None


def test_claim_next_due_batch_groups_due_messages_by_chat(monkeypatch, sqlite_session):
    @contextmanager
    def fake_session_scope():
        yield sqlite_session
        sqlite_session.commit()

    monkeypatch.setattr("dobby_app.services.messages.batches.session_scope", fake_session_scope)
    monkeypatch.setattr("dobby_app.services.messages.batches.settings.telegram_batch_debounce_seconds", 30)
    monkeypatch.setattr("dobby_app.services.messages.batches.settings.telegram_batch_stale_processing_seconds", 300)
    now = datetime(2026, 6, 13, 12, 0, 0)
    for message_id, chat_id, text in [(501, 1, "one"), (502, 1, "two"), (503, 2, "other chat")]:
        sqlite_session.add(
            TelegramMessage(
                update_id=None,
                message_id=message_id,
                chat_id=chat_id,
                sender_id=chat_id,
                text=text,
                kind="text",
                created_at=now - timedelta(seconds=45),
                raw={},
            )
        )
    sqlite_session.commit()

    rows = claim_next_due_batch(now=now)

    assert [row.message_id for row in rows or []] == [501, 502]
    assert all(row.planner_batch_id for row in rows or [])


def test_claim_next_due_batch_excludes_processed_and_reclaims_stale(monkeypatch, sqlite_session):
    @contextmanager
    def fake_session_scope():
        yield sqlite_session
        sqlite_session.commit()

    monkeypatch.setattr("dobby_app.services.messages.batches.session_scope", fake_session_scope)
    monkeypatch.setattr("dobby_app.services.messages.batches.settings.telegram_batch_debounce_seconds", 30)
    monkeypatch.setattr("dobby_app.services.messages.batches.settings.telegram_batch_stale_processing_seconds", 300)
    now = datetime(2026, 6, 13, 12, 0, 0)
    sqlite_session.add_all(
        [
            TelegramMessage(
                update_id=None,
                message_id=601,
                chat_id=1,
                sender_id=1,
                text="done",
                kind="text",
                created_at=now - timedelta(minutes=10),
                planner_processed_at=now - timedelta(minutes=9),
                raw={},
            ),
            TelegramMessage(
                update_id=None,
                message_id=602,
                chat_id=1,
                sender_id=1,
                text="stale",
                kind="text",
                created_at=now - timedelta(minutes=10),
                planner_processing_started_at=now - timedelta(minutes=6),
                raw={},
            ),
        ]
    )
    sqlite_session.commit()

    rows = claim_next_due_batch(now=now)

    assert [row.message_id for row in rows or []] == [602]


def test_batch_context_uses_prior_processed_history(monkeypatch, sqlite_session):
    @contextmanager
    def fake_session_scope():
        yield sqlite_session
        sqlite_session.commit()

    monkeypatch.setattr("dobby_app.services.messages.batches.session_scope", fake_session_scope)
    monkeypatch.setattr("dobby_app.services.messages.history.session_scope", fake_session_scope)
    now = datetime(2026, 6, 13, 12, 0, 0)
    sqlite_session.add_all(
        [
            TelegramMessage(
                update_id=None,
                message_id=701,
                chat_id=1,
                sender_id=1,
                text="processed old",
                kind="text",
                created_at=now - timedelta(minutes=3),
                planner_processed_at=now - timedelta(minutes=2),
                raw={},
            ),
            TelegramMessage(
                update_id=None,
                message_id=702,
                chat_id=1,
                sender_id=1,
                text="unprocessed old",
                kind="text",
                created_at=now - timedelta(minutes=2),
                raw={},
            ),
            TelegramMessage(
                update_id=None,
                message_id=703,
                chat_id=1,
                sender_id=1,
                text="new task",
                kind="text",
                created_at=now - timedelta(minutes=1),
                raw={},
            ),
        ]
    )
    sqlite_session.commit()

    rows = sqlite_session.query(TelegramMessage).filter(TelegramMessage.message_id == 703).all()
    context = batch_conversation_context(rows)

    assert context[0] == {"role": "user", "content": "processed old"}
    assert "unprocessed old" not in str(context)
    assert "message_id=703" in context[-1]["content"]
    assert "new task" in context[-1]["content"]


def test_process_claimed_batch_replies_to_task_source_message(monkeypatch, sqlite_session):
    @contextmanager
    def fake_session_scope():
        yield sqlite_session
        sqlite_session.commit()

    sent = []

    class FakeBot:
        async def send_message(self, chat_id, text, **kwargs):
            sent.append((chat_id, text, kwargs))
            return SimpleNamespace(
                message_id=900 + len(sent),
                from_user=SimpleNamespace(id=0),
                model_dump=lambda mode="json": {"message_id": 900 + len(sent)},
            )

    async def fake_plan_actions(text, conversation_context=None, tool_results=None):
        return ActionPlan(
            tasks=[
                PlannedTask(
                    source_message_ids=[801],
                    actions=[PlannedAction(tool="message", operation="send", arguments={"content": "First"})],
                ),
                PlannedTask(
                    source_message_ids=[802],
                    actions=[PlannedAction(tool="message", operation="send", arguments={"content": "Second"})],
                ),
            ],
            confidence=0.9,
        )

    async def fake_execute_tool_action(action, latest_text, conversation_context=None):
        return ToolExecutionResult(
            tool="message",
            operation="send",
            status="success",
            message=action.arguments["content"],
        )

    monkeypatch.setattr("dobby_app.services.messages.batches.session_scope", fake_session_scope)
    monkeypatch.setattr("dobby_app.services.messages.history.session_scope", fake_session_scope)
    monkeypatch.setattr("dobby_app.services.messages.batches.plan_actions", fake_plan_actions)
    monkeypatch.setattr("dobby_app.assistant.planner_runner.execute_tool_action", fake_execute_tool_action)
    rows = []
    for message_id, text in [(801, "task one"), (802, "task two")]:
        row = TelegramMessage(
            update_id=None,
            message_id=message_id,
            chat_id=1,
            sender_id=1,
            text=text,
            kind="text",
            raw={},
        )
        sqlite_session.add(row)
        rows.append(row)
    sqlite_session.commit()

    asyncio.run(process_claimed_batch(FakeBot(), rows))

    assert [call[2]["reply_to_message_id"] for call in sent] == [801, 802]
    assert sqlite_session.query(TelegramMessage).filter_by(kind="assistant").count() == 2


def test_slash_command_executes_through_command_tool(monkeypatch, sqlite_session):
    @contextmanager
    def fake_session_scope():
        yield sqlite_session
        sqlite_session.commit()

    monkeypatch.setattr("dobby_app.assistant.tool_dispatch.session_scope", fake_session_scope)

    result = asyncio.run(
        execute_tool_action(
            PlannedAction(
                tool="command",
                operation="execute",
                arguments={"command": "/status"},
            ),
            "/status",
        )
    )

    assert result.tool == "command"
    assert result.status == "success"
    assert "DOBBY is running" in result.message


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

    monkeypatch.setattr("dobby_app.assistant.planner_runner.plan_actions", fake_plan_actions)

    async def fake_execute_tool_action(action, latest_text, conversation_context=None):
        return ToolExecutionResult(
            tool="message",
            operation="send",
            status="success",
            message=action.arguments["content"],
        )

    monkeypatch.setattr("dobby_app.assistant.planner_runner.execute_tool_action", fake_execute_tool_action)

    response = asyncio.run(handle_plain_text("Latest message", context))

    assert response == "Assistant answer"
    assert calls == [
        ("plan", "Latest message", context),
    ]
