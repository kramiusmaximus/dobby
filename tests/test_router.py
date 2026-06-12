from __future__ import annotations

import asyncio
from types import SimpleNamespace

from dobby_app.context_templates import load_context_template
from dobby_app.router import _planner_system_prompt, assistant_chat, plan_actions


def test_planner_context_mentions_durable_daily_and_weekly_plans():
    prompt = _planner_system_prompt()

    assert "Daily plans, weekly plans" in prompt
    assert 'A reply to "What do you plan to accomplish today?" is a daily plan' in prompt
    assert "Preserve these unless Mark is clearly only chatting" in prompt


def test_planner_context_does_not_document_executor_operations():
    prompt = _planner_system_prompt()

    assert "wiki.create" not in prompt
    assert "wiki.update" not in prompt
    assert "calendar.create" not in prompt
    assert "message.send" not in prompt


def test_tool_contexts_document_executor_operations():
    message_context = load_context_template("tools/message.md")
    calendar_context = load_context_template("tools/calendar.md")
    wiki_context = load_context_template("tools/wiki.md")

    assert "Available tools" in message_context
    assert "Available tools" in calendar_context
    assert "Available tools" in wiki_context
    assert "Format Telegram messages as HTML, not Markdown." in message_context
    assert "<b>important text</b>" in message_context
    assert "obsidian_write" in wiki_context
    assert "Do not guess paths or targets." in wiki_context


def test_planner_uses_planner_model(monkeypatch):
    calls = []

    class FakeResponses:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                output_text=(
                    '{"confidence": 0.9, "actions": [{"tool": "message", "operation": "send", '
                    '"reason": null, "arguments": {"kind": null, "title": null, "datetime": null, '
                    '"duration_minutes": null, "alarm_minutes_before": null, "days": null, '
                    '"query": null, "content": "Hi", "path": null, "exact_line": null, '
                    '"replacement": null}}]}'
                )
            )

    class FakeAsyncOpenAI:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.responses = FakeResponses()

    monkeypatch.setattr("dobby_app.router.AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr("dobby_app.router.settings.openai_api_key", "test-key")
    monkeypatch.setattr("dobby_app.router.settings.planner_model", "planner-test-model")
    monkeypatch.setattr("dobby_app.router.settings.planner_reasoning_effort", "low")

    plan = asyncio.run(plan_actions("hello"))

    assert plan.actions[0].tool == "message"
    assert calls[0]["model"] == "planner-test-model"
    assert calls[0]["reasoning"] == {"effort": "low"}


def test_assistant_fallback_uses_executioner_model(monkeypatch):
    calls = []

    class FakeResponses:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_text="Fallback answer")

    class FakeAsyncOpenAI:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.responses = FakeResponses()

    monkeypatch.setattr("dobby_app.router.AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr("dobby_app.router.settings.openai_api_key", "test-key")
    monkeypatch.setattr("dobby_app.router.settings.executioner_model", "executioner-test-model")
    monkeypatch.setattr("dobby_app.router.settings.executioner_reasoning_effort", "medium")

    response = asyncio.run(assistant_chat("hello"))

    assert response == "Fallback answer"
    assert calls[0]["model"] == "executioner-test-model"
    assert calls[0]["reasoning"] == {"effort": "medium"}
