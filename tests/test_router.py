from __future__ import annotations

from dobby_app.context_templates import load_context_template
from dobby_app.router import _planner_system_prompt


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

    assert "Supported operation" in message_context
    assert "Supported operations" in calendar_context
    assert "Supported operations" in wiki_context
    assert "Do not perform arbitrary wiki rewrites." in wiki_context
    assert "`exact_line`" in wiki_context
