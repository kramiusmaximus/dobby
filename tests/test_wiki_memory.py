from __future__ import annotations

from datetime import datetime

import pytest

from dobby_app.integrations.obsidian import ObsidianHTTPError
from dobby_app.services.wiki_memory import delete_wiki_line, sync_calendar_item_to_wiki, update_wiki_line


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
    monkeypatch.setattr("dobby_app.services.wiki_memory.obsidian_is_enabled", lambda: True)
    monkeypatch.setattr("dobby_app.services.wiki_memory.get_obsidian_client", lambda: client)

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


def test_update_wiki_line_replaces_one_exact_line(monkeypatch):
    class FakeObsidianClient:
        def __init__(self):
            self.content = "# Note\n\n- Old line\n"
            self.calls = []

        def read(self, path):
            self.calls.append(("read", path))
            return self.content if path == "pages/goals/example.md" else "# Log\n"

        def write(self, path, content):
            self.calls.append(("write", path, content))
            self.content = content
            return ""

        def patch(self, *args, **kwargs):
            self.calls.append(("patch", args, kwargs))
            return ""

        def append(self, *args, **kwargs):
            self.calls.append(("append", args, kwargs))
            return ""

    client = FakeObsidianClient()
    monkeypatch.setattr("dobby_app.services.wiki_memory.obsidian_is_enabled", lambda: True)
    monkeypatch.setattr("dobby_app.services.wiki_memory.get_obsidian_client", lambda: client)

    response = update_wiki_line(
        path="pages/goals/example.md",
        exact_line="- Old line",
        replacement="- New line",
        reason="test",
    )

    assert response == "Updated wiki line in pages/goals/example.md."
    assert client.content == "# Note\n\n- New line\n"
    assert any(call[0] == "append" and "memory-update" in call[1][1] for call in client.calls)


def test_delete_wiki_line_removes_one_exact_line(monkeypatch):
    class FakeObsidianClient:
        def __init__(self):
            self.content = "# Note\n\n- Keep\n- Remove\n"

        def read(self, path):
            return self.content if path == "pages/goals/example.md" else "# Log\n"

        def write(self, path, content):
            self.content = content
            return ""

        def patch(self, *args, **kwargs):
            return ""

        def append(self, *args, **kwargs):
            return ""

    client = FakeObsidianClient()
    monkeypatch.setattr("dobby_app.services.wiki_memory.obsidian_is_enabled", lambda: True)
    monkeypatch.setattr("dobby_app.services.wiki_memory.get_obsidian_client", lambda: client)

    response = delete_wiki_line(
        path="pages/goals/example.md",
        exact_line="- Remove",
        reason="test",
    )

    assert response == "Deleted wiki line from pages/goals/example.md."
    assert client.content == "# Note\n\n- Keep\n"


def test_delete_wiki_line_succeeds_when_log_append_404s(monkeypatch):
    class FakeObsidianClient:
        def __init__(self):
            self.content = "# Note\n\n- Keep\n- Remove\n"

        def read(self, path):
            return self.content if path == "pages/goals/example.md" else "# Log\n"

        def write(self, path, content):
            self.content = content
            return ""

        def patch(self, *args, **kwargs):
            return ""

        def append(self, path, content, **kwargs):
            if path == "log.md":
                raise ObsidianHTTPError("not found", status_code=404)
            return ""

    client = FakeObsidianClient()
    monkeypatch.setattr("dobby_app.services.wiki_memory.obsidian_is_enabled", lambda: True)
    monkeypatch.setattr("dobby_app.services.wiki_memory.get_obsidian_client", lambda: client)

    response = delete_wiki_line(
        path="pages/goals/example.md",
        exact_line="- Remove",
        reason="test",
    )

    assert response == "Deleted wiki line from pages/goals/example.md."
    assert client.content == "# Note\n\n- Keep\n"


def test_delete_wiki_line_refuses_ambiguous_line(monkeypatch):
    class FakeObsidianClient:
        def read(self, path):
            return "# Note\n\n- Duplicate\n- Duplicate\n"

    monkeypatch.setattr("dobby_app.services.wiki_memory.obsidian_is_enabled", lambda: True)
    monkeypatch.setattr("dobby_app.services.wiki_memory.get_obsidian_client", lambda: FakeObsidianClient())

    with pytest.raises(ValueError, match="appears more than once"):
        delete_wiki_line(path="pages/goals/example.md", exact_line="- Duplicate")
