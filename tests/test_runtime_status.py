from __future__ import annotations

from dobby_app import runtime_status


def test_current_commit_prefers_env(monkeypatch):
    monkeypatch.setenv("DOBBY_COMMIT", "1234567890abcdef")

    assert runtime_status.current_commit() == "1234567890ab"


def test_format_startup_message_includes_commit_and_status():
    message = runtime_status.format_startup_message(
        "poller",
        {
            "ok": True,
            "service": "poller",
            "commit": "abc123",
            "telegram_poll_interval_seconds": 60,
            "obsidian_enabled": True,
        },
    )

    assert "DOBBY deployed" in message
    assert "Commit: abc123" in message
    assert "Status: ok" in message
    assert "Obsidian: enabled" in message
