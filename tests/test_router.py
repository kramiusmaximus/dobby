from __future__ import annotations

from dobby_app.context_templates import load_context_template
from dobby_app.router import _planner_system_prompt


def test_planner_context_mentions_durable_daily_and_weekly_plans():
    prompt = _planner_system_prompt()

    assert "Daily plans, weekly plans" in prompt
    assert 'A reply to "What do you plan to accomplish today?" is a daily plan' in prompt
    assert "wiki.create" in prompt


def test_executor_context_documents_safe_wiki_mutations():
    context = load_context_template("executor.md")

    assert "Do not perform arbitrary wiki rewrites." in context
    assert "wiki.update` requires" in context
    assert "wiki.delete` requires" in context
