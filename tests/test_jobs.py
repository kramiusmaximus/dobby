from __future__ import annotations

import asyncio
from datetime import timedelta

from dobby_app.services.jobs import _daily_briefing, _telegram_reconciliation


def test_daily_briefing_sends_four_formatted_messages(monkeypatch):
    sent = []
    captured = {}

    class FakeObsidianClient:
        def list(self, path):
            if path == "pages/goals":
                return ["gift.md"]
            return []

        def read(self, path):
            assert path == "pages/goals/gift.md"
            return """---
title: Gift
type: goal
created: 2026-06-08
updated: 2026-06-08
status: active
tags: []
sources: []
---

# Gift

## Goal

Buy the present before the birthday.
"""

    def fake_list_items(start, end):
        captured["start"] = start
        captured["end"] = end
        return [
            {"summary": "Dentist", "start": start.replace(hour=9)},
            {"summary": "Birthday", "start": start.date()},
            {"summary": "Studio", "start": start + timedelta(days=3, hours=15)},
        ]

    async def fake_send_telegram_message(text):
        sent.append(text)

    monkeypatch.setattr("dobby_app.services.daily_briefing.random.choice", lambda options: options[0])
    monkeypatch.setattr("dobby_app.services.daily_briefing.list_items", fake_list_items)
    monkeypatch.setattr("dobby_app.services.daily_briefing.send_telegram_message", fake_send_telegram_message)
    monkeypatch.setattr("dobby_app.services.daily_briefing.obsidian_is_enabled", lambda: True)
    monkeypatch.setattr("dobby_app.services.daily_briefing.get_obsidian_client", lambda: FakeObsidianClient())

    result = asyncio.run(_daily_briefing())

    assert result == {"sent": True, "upcoming_count": 3}
    assert len(sent) == 4
    assert sent[0].startswith("Start\n\n")
    assert "Calendar and Reminders" in sent[1]
    assert "Today\n- " in sent[1]
    assert "Dentist" in sent[1]
    assert "all day - Birthday" in sent[1]
    assert "time unknown - Birthday" not in sent[1]
    assert "Next 2 Weeks\n- " in sent[1]
    assert "Studio" in sent[1]
    assert sent[2].startswith("Other Important Reminders\n\n")
    assert "Gift: Buy the present before the birthday." in sent[2]
    assert sent[3] == "Today\n\nWhat do you plan to accomplish today?"
    assert captured["start"].hour == 0
    assert captured["start"].minute == 0
    assert (captured["end"] - captured["start"]).days == 14


def test_telegram_reconciliation_job_is_silent(monkeypatch):
    sent = []

    async def fake_send_telegram_message(text):
        sent.append(text)

    monkeypatch.setattr("dobby_app.services.jobs.send_telegram_message", fake_send_telegram_message)

    result = asyncio.run(_telegram_reconciliation())

    assert result == {"sent": False, "skipped": True}
    assert sent == []
