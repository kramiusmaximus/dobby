from __future__ import annotations

import asyncio

from dobby_app.telegram_client import send_telegram_message


def test_telegram_client_sends_html_parse_mode(monkeypatch):
    calls = []

    class FakeSession:
        async def close(self):
            calls.append(("close",))

    class FakeBot:
        session = FakeSession()

        async def send_message(self, **kwargs):
            calls.append(("send_message", kwargs))

    monkeypatch.setattr("dobby_app.telegram_client.settings.telegram_user_id", 123)
    monkeypatch.setattr("dobby_app.telegram_client.get_bot", lambda: FakeBot())

    asyncio.run(send_telegram_message("Birthday is on <b>8 July 2026</b>."))

    assert calls[0] == (
        "send_message",
        {
            "chat_id": 123,
            "text": "Birthday is on <b>8 July 2026</b>.",
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
    )
    assert calls[1] == ("close",)
