from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from dobby_app.message_handler import _is_daily_plan_reply, _message_already_recorded, _save_daily_plan_response
from dobby_app.models import TelegramMessage


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
