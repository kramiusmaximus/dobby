from __future__ import annotations

import asyncio
from types import SimpleNamespace

from dobby_app.router import PlannedAction
from dobby_app.executioners.calendar import execute_calendar_action
from dobby_app.executioners.message import execute_message_action
from dobby_app.executioners.wiki import execute_wiki_action


class FakeResponses:
    def __init__(self, call):
        self.call = call
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            id="response-1",
            output_text="",
            output=[
                {
                    "type": "function_call",
                    "call_id": "call-1",
                    "name": self.call["name"],
                    "arguments": self.call["arguments"],
                }
            ],
        )


def _patch_openai(monkeypatch, fake_responses):
    class FakeAsyncOpenAI:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.responses = fake_responses

    monkeypatch.setattr("dobby_app.llm_client.AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr("dobby_app.executioner_agent.settings.openai_api_key", "test-key")
    monkeypatch.setattr("dobby_app.executioner_agent.settings.executioner_model", "executioner-test-model")
    monkeypatch.setattr("dobby_app.executioner_agent.settings.executioner_reasoning_effort", "medium")


def test_message_executioner_uses_context_and_executor_model(monkeypatch):
    responses = FakeResponses({"name": "message_send", "arguments": '{"content": "Handled"}'})
    _patch_openai(monkeypatch, responses)

    result = asyncio.run(
        execute_message_action(
            PlannedAction(tool="message", operation="send", arguments={"content": "Handled"}),
            "latest",
            [{"role": "user", "content": "context"}],
        )
    )

    assert result.status == "success"
    assert result.message == "Handled"
    assert responses.requests[0]["model"] == "executioner-test-model"
    assert responses.requests[0]["reasoning"] == {"effort": "medium"}
    assert "You produce Telegram text for Mark." in responses.requests[0]["input"][0]["content"]


def test_message_executioner_can_request_reaction(monkeypatch):
    responses = FakeResponses({"name": "message_react", "arguments": '{"emoji": "✅"}'})
    _patch_openai(monkeypatch, responses)

    result = asyncio.run(
        execute_message_action(
            PlannedAction(tool="message", operation="send", arguments={}),
            "latest",
        )
    )

    assert result.status == "success"
    assert result.message is None
    assert result.data == {"reaction_emoji": "✅"}


def test_wiki_executioner_calls_raw_write_wrapper(monkeypatch):
    responses = FakeResponses(
        {
            "name": "obsidian_write",
            "arguments": '{"path": "pages/goals/example.md", "content": "# Updated\\n"}',
        }
    )
    _patch_openai(monkeypatch, responses)
    calls = []

    class FakeObsidianClient:
        def write(self, path, content):
            calls.append((path, content))
            return "ok"

    monkeypatch.setattr("dobby_app.wiki_service.obsidian_is_enabled", lambda: True)
    monkeypatch.setattr("dobby_app.wiki_service.get_obsidian_client", lambda: FakeObsidianClient())

    result = asyncio.run(
        execute_wiki_action(
            PlannedAction(tool="wiki", operation="update", arguments={}),
            "latest",
        )
    )

    assert result.status == "success"
    assert result.message == "ok"
    assert calls == [("pages/goals/example.md", "# Updated\n")]
    assert "You execute DOBBY wiki" in responses.requests[0]["input"][0]["content"]


def test_wiki_executioner_answers_memory_query_with_obsidian_tool_loop(monkeypatch):
    class FakeLoopResponses:
        def __init__(self):
            self.requests = []

        async def create(self, **kwargs):
            self.requests.append(kwargs)
            if len(self.requests) == 1:
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
            assert kwargs["previous_response_id"] == "response-1"
            assert kwargs["input"][0]["type"] == "function_call_output"
            return SimpleNamespace(
                id="response-2",
                output_text="Studio context lives in pages/projects/studio.md.",
                output=[],
            )

    responses = FakeLoopResponses()
    _patch_openai(monkeypatch, responses)

    class FakeObsidianClient:
        def read(self, path):
            assert path == "index.md"
            return "# Index\n\n- [[Studio Project]]"

    monkeypatch.setattr("dobby_app.wiki_service.obsidian_is_enabled", lambda: True)
    monkeypatch.setattr("dobby_app.wiki_service.get_obsidian_client", lambda: FakeObsidianClient())

    result = asyncio.run(
        execute_wiki_action(
            PlannedAction(tool="wiki", operation="read", arguments={"query": "TouchDesigner"}),
            "TouchDesigner",
        )
    )

    assert result.status == "success"
    assert result.message == "Studio context lives in pages/projects/studio.md."
    assert responses.requests[0]["model"] == "executioner-test-model"
    assert responses.requests[0]["reasoning"] == {"effort": "medium"}
    assert responses.requests[1]["model"] == "executioner-test-model"
    assert responses.requests[1]["reasoning"] == {"effort": "medium"}


def test_wiki_executioner_requires_path_for_delete(monkeypatch):
    responses = FakeResponses(
        {
            "name": "obsidian_delete",
            "arguments": '{"path": null}',
        }
    )
    _patch_openai(monkeypatch, responses)

    result = asyncio.run(
        execute_wiki_action(
            PlannedAction(tool="wiki", operation="delete", arguments={"path": "pages/goals/example.md"}),
            "latest",
        )
    )

    assert result.status == "needs_clarification"
    assert result.message == "Which wiki path should I delete?"


def test_calendar_executioner_calls_create_wrapper(monkeypatch):
    responses = FakeResponses(
        {
            "name": "calendar_create_item",
            "arguments": (
                '{"title": "Call dentist", "datetime": "tomorrow 9", '
                '"kind": "reminder", "duration_minutes": 30, '
                '"alarm_minutes_before": null, "calendar_name": null}'
            ),
        }
    )
    _patch_openai(monkeypatch, responses)

    monkeypatch.setattr(
        "dobby_app.executioners.calendar_tools.create_execution_calendar_item",
        lambda title, starts_at, item_type, alarm_minutes_before, duration_minutes, calendar_name: (
            f"Created {item_type}: {title} at parsed."
        ),
    )

    result = asyncio.run(
        execute_calendar_action(
            PlannedAction(tool="calendar", operation="create", arguments={}),
            "remind me to call dentist tomorrow at 9",
        )
    )

    assert result.status == "success"
    assert result.message == "Created reminder: Call dentist at parsed."
    assert result.data == {
        "title": "Call dentist",
        "datetime": "tomorrow 9",
        "kind": "reminder",
        "duration_minutes": 30,
        "calendar_name": None,
    }
    assert "You execute DOBBY calendar" in responses.requests[0]["input"][0]["content"]


def test_calendar_delete_calls_delete_wrapper(monkeypatch):
    responses = FakeResponses(
        {
            "name": "calendar_delete_item",
            "arguments": '{"uid": "event-uid", "calendar_name": null}',
        }
    )
    _patch_openai(monkeypatch, responses)
    calls = []
    monkeypatch.setattr(
        "dobby_app.executioners.calendar_tools.delete_execution_calendar_item",
        lambda **kwargs: calls.append(kwargs),
    )

    result = asyncio.run(
        execute_calendar_action(
            PlannedAction(tool="calendar", operation="delete", arguments={}),
            "delete the dentist reminder",
        )
    )

    assert result.status == "success"
    assert result.message == "Deleted calendar item: event-uid."
    assert calls == [{"uid": "event-uid", "calendar_name": None}]
