from __future__ import annotations

from types import SimpleNamespace

from dobby_app.message_handler import _is_daily_plan_reply, _save_daily_plan_response


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
