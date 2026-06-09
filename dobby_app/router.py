from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI

from dobby_app.config import settings
from dobby_app.context_templates import load_context_template

ConversationMessage = dict[str, str]


@dataclass(frozen=True)
class PlannedAction:
    tool: str
    operation: str | None
    arguments: dict
    reason: str | None = None


@dataclass(frozen=True)
class ActionPlan:
    actions: list[PlannedAction]
    confidence: float


ACTION_PLAN_SCHEMA = {
    "name": "dobby_action_plan",
    "type": "json_schema",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "confidence": {"type": "number"},
            "actions": {
                "type": "array",
                "minItems": 1,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "tool": {"type": "string", "enum": ["message", "calendar", "wiki"]},
                        "operation": {
                            "type": ["string", "null"],
                            "enum": ["create", "read", "update", "delete", "send", "none", None],
                        },
                        "reason": {"type": ["string", "null"]},
                        "arguments": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "kind": {"type": ["string", "null"], "enum": ["reminder", "event", "item", None]},
                                "title": {"type": ["string", "null"]},
                                "datetime": {"type": ["string", "null"]},
                                "duration_minutes": {"type": ["integer", "null"]},
                                "alarm_minutes_before": {"type": ["integer", "null"]},
                                "days": {"type": ["integer", "null"]},
                                "query": {"type": ["string", "null"]},
                                "content": {"type": ["string", "null"]},
                                "path": {"type": ["string", "null"]},
                                "exact_line": {"type": ["string", "null"]},
                                "replacement": {"type": ["string", "null"]},
                            },
                            "required": [
                                "kind",
                                "title",
                                "datetime",
                                "duration_minutes",
                                "alarm_minutes_before",
                                "days",
                                "query",
                                "content",
                                "path",
                                "exact_line",
                                "replacement",
                            ],
                        },
                    },
                    "required": ["tool", "operation", "reason", "arguments"],
                },
            },
        },
        "required": ["confidence", "actions"],
    },
}


def _llm_input(
    system_prompt: str,
    text: str,
    conversation_context: list[ConversationMessage] | None,
) -> list[ConversationMessage]:
    messages: list[ConversationMessage] = [{"role": "system", "content": system_prompt}]
    if conversation_context:
        messages.extend(conversation_context)
    else:
        messages.append({"role": "user", "content": text})
    return messages


async def plan_actions(text: str, conversation_context: list[ConversationMessage] | None = None) -> ActionPlan:
    if not settings.openai_api_key:
        return ActionPlan(
            actions=[
                PlannedAction(
                    tool="message",
                    operation="send",
                    arguments={"content": "I can route commands, but OPENAI_API_KEY is not configured yet."},
                )
            ],
            confidence=0.0,
        )

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.responses.create(
        model=settings.router_model,
        input=_llm_input(
            _planner_system_prompt(),
            text,
            conversation_context,
        ),
        text={"format": ACTION_PLAN_SCHEMA},
    )
    payload = json.loads(response.output_text)
    actions = [
        PlannedAction(
            tool=item["tool"],
            operation=item.get("operation"),
            reason=item.get("reason"),
            arguments=item.get("arguments") or {},
        )
        for item in payload.get("actions", [])
    ]
    return ActionPlan(
        actions=actions,
        confidence=float(payload.get("confidence") or 0),
    )


def _planner_system_prompt() -> str:
    now = datetime.now(ZoneInfo(settings.app_timezone))
    return (
        load_context_template("planner.md")
        .replace("{current_date}", now.date().isoformat())
        .replace("{timezone}", settings.app_timezone)
    )


async def assistant_chat(text: str, conversation_context: list[ConversationMessage] | None = None) -> str:
    if not settings.openai_api_key:
        return "I can route commands, but OPENAI_API_KEY is not configured yet."

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.responses.create(
        model=settings.assistant_model,
        input=_llm_input(
            "You are DOBBY, Mark's personal assistant. Be concise and useful in Telegram.",
            text,
            conversation_context,
        ),
    )
    return response.output_text.strip()
