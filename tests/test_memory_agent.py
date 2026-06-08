from __future__ import annotations

import asyncio
from types import SimpleNamespace

from dobby_app.memory_agent import answer_memory_query


def test_answer_memory_query_requires_obsidian(monkeypatch):
    monkeypatch.setattr("dobby_app.memory_agent.obsidian_is_enabled", lambda: False)

    response = asyncio.run(answer_memory_query("TouchDesigner"))

    assert "Obsidian API is not configured" in response


def test_answer_memory_query_uses_obsidian_tool_loop(monkeypatch):
    class FakeObsidianClient:
        def __init__(self):
            self.calls = []

        def health(self):
            self.calls.append(("health",))
            return {"authenticated": True}

        def read(self, path):
            self.calls.append(("read", path))
            return "# Index\n\n- [[Studio Project]]"

        def search_simple(self, query):
            self.calls.append(("search_simple", query))
            return [{"filename": "pages/projects/studio.md", "score": 1}]

    obsidian = FakeObsidianClient()
    monkeypatch.setattr("dobby_app.memory_agent.obsidian_is_enabled", lambda: True)
    monkeypatch.setattr("dobby_app.memory_agent.get_obsidian_client", lambda: obsidian)
    monkeypatch.setattr("dobby_app.memory_agent.settings.openai_api_key", "test-key")

    class FakeResponses:
        def __init__(self):
            self.calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(
                    id="response-1",
                    output_text="",
                    output=[
                        {
                            "type": "function_call",
                            "call_id": "call-1",
                            "name": "obsidian_read",
                            "arguments": '{"path": "index.md"}',
                        }
                    ],
                )
            if self.calls == 2:
                assert kwargs["previous_response_id"] == "response-1"
                return SimpleNamespace(
                    id="response-2",
                    output_text="",
                    output=[
                        {
                            "type": "function_call",
                            "call_id": "call-2",
                            "name": "obsidian_search_simple",
                            "arguments": '{"query": "TouchDesigner"}',
                        }
                    ],
                )
            return SimpleNamespace(
                id="response-3",
                output_text="Studio context lives in pages/projects/studio.md.",
                output=[],
            )

    fake_responses = FakeResponses()

    class FakeAsyncOpenAI:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.responses = fake_responses

    monkeypatch.setattr("dobby_app.memory_agent.AsyncOpenAI", FakeAsyncOpenAI)

    response = asyncio.run(answer_memory_query("TouchDesigner"))

    assert response == "Studio context lives in pages/projects/studio.md."
    assert ("health",) in obsidian.calls
    assert ("read", "index.md") in obsidian.calls
    assert ("search_simple", "TouchDesigner") in obsidian.calls
