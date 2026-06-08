from __future__ import annotations

from datetime import datetime

from dobby_app.wiki_memory import sync_calendar_item_to_wiki


def test_calendar_sync_writes_through_obsidian(monkeypatch):
    class FakeObsidianClient:
        def __init__(self):
            self.calls = []

        def read(self, path):
            self.calls.append(("read", path))
            if path == "pages/calendar/june-2026-commitments.md":
                return "# June 2026 Commitments\n"
            return "# Log\n"

        def write(self, *args, **kwargs):
            self.calls.append(("write", args, kwargs))
            return ""

        def patch(self, *args, **kwargs):
            self.calls.append(("patch", args, kwargs))
            return ""

        def append(self, *args, **kwargs):
            self.calls.append(("append", args, kwargs))
            return ""

    client = FakeObsidianClient()
    monkeypatch.setattr("dobby_app.wiki_memory.obsidian_is_enabled", lambda: True)
    monkeypatch.setattr("dobby_app.wiki_memory.get_obsidian_client", lambda: client)

    rel_path = sync_calendar_item_to_wiki(
        title="Studio visit",
        starts_at=datetime(2026, 6, 12, 15, 0),
        item_type="event",
    )

    assert rel_path == "pages/calendar/june-2026-commitments.md"
    assert any(call[0] == "patch" for call in client.calls)
    assert any(
        call[0] == "append" and "Studio visit" in call[1][1]
        for call in client.calls
    )
