from __future__ import annotations

import json
from dataclasses import dataclass

from openai import AsyncOpenAI

from dobby_app.config import settings


@dataclass(frozen=True)
class RoutedAction:
    action: str
    arguments: dict
    confidence: float
    clarification: str | None = None


ROUTER_SCHEMA = {
    "name": "dobby_route",
    "type": "json_schema",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "create_calendar_reminder",
                    "create_calendar_event",
                    "list_upcoming",
                    "daily_briefing",
                    "wiki_query",
                    "chat",
                    "clarify",
                ],
            },
            "confidence": {"type": "number"},
            "clarification": {"type": ["string", "null"]},
            "arguments": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": ["string", "null"]},
                    "datetime": {"type": ["string", "null"]},
                    "duration_minutes": {"type": ["integer", "null"]},
                    "alarm_minutes_before": {"type": ["integer", "null"]},
                    "query": {"type": ["string", "null"]},
                },
                "required": ["title", "datetime", "duration_minutes", "alarm_minutes_before", "query"],
            },
        },
        "required": ["action", "confidence", "clarification", "arguments"],
    },
}


async def route_message(text: str) -> RoutedAction:
    if not settings.openai_api_key:
        return RoutedAction(
            action="chat",
            arguments={"query": text},
            confidence=0.0,
            clarification=None,
        )

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.responses.create(
        model=settings.router_model,
        input=[
            {
                "role": "system",
                "content": (
                    "You route Mark's Telegram message to one DOBBY tool. "
                    "Use calendar reminders for reminders: a timed calendar event with an alarm. "
                    "If date/time or title is missing for event/reminder creation, choose clarify."
                ),
            },
            {"role": "user", "content": text},
        ],
        text={"format": ROUTER_SCHEMA},
    )
    payload = json.loads(response.output_text)
    return RoutedAction(
        action=payload["action"],
        arguments=payload.get("arguments") or {},
        confidence=float(payload.get("confidence") or 0),
        clarification=payload.get("clarification"),
    )


async def assistant_chat(text: str) -> str:
    if not settings.openai_api_key:
        return "I can route commands, but OPENAI_API_KEY is not configured yet."

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.responses.create(
        model=settings.assistant_model,
        input=[
            {
                "role": "system",
                "content": "You are DOBBY, Mark's personal assistant. Be concise and useful in Telegram.",
            },
            {"role": "user", "content": text},
        ],
    )
    return response.output_text.strip()
