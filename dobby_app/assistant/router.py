from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any
from zoneinfo import ZoneInfo

from dobby_app.config.settings import settings
from dobby_app.utils.context_templates import load_context_template
from dobby_app.integrations.openai import create_response
from dobby_app.assistant.llm_logging import action_plan_for_log, truncate_for_log

ConversationMessage = dict[str, str]
logger = logging.getLogger(__name__)


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
    tool_results: list[dict[str, Any]] | None = None,
) -> list[ConversationMessage]:
    messages: list[ConversationMessage] = [{"role": "system", "content": system_prompt}]
    if conversation_context:
        messages.extend(conversation_context)
    else:
        messages.append({"role": "user", "content": text})
    if tool_results:
        messages.append(
            {
                "role": "user",
                "content": (
                    "Tool executor results from the previous plan:\n"
                    f"{json.dumps(tool_results, ensure_ascii=False, default=str)}\n\n"
                    "Decide the next plan. If enough work is complete, respond to Mark. "
                    "If something is not found or ambiguous, ask a concise clarification."
                ),
            }
        )
    return messages


async def plan_actions(
    text: str,
    conversation_context: list[ConversationMessage] | None = None,
    tool_results: list[dict[str, Any]] | None = None,
) -> ActionPlan:
    logger.info(
        "Planner starting: model=%s reasoning_effort=%s text=%s conversation_messages=%s tool_results=%s",
        settings.planner_model,
        settings.planner_reasoning_effort,
        truncate_for_log(text),
        len(conversation_context or []),
        truncate_for_log(json.dumps(tool_results, ensure_ascii=False, default=str)) if tool_results else None,
    )
    if not settings.openai_api_key:
        plan = ActionPlan(
            actions=[
                PlannedAction(
                    tool="message",
                    operation="send",
                    arguments={"content": "I can route commands, but OPENAI_API_KEY is not configured yet."},
                )
            ],
            confidence=0.0,
        )
        logger.info("Planner fallback plan: %s", action_plan_for_log(plan))
        return plan

    response = await create_response(
        api_key=settings.openai_api_key,
        model=settings.planner_model,
        reasoning_effort=settings.planner_reasoning_effort,
        input=_llm_input(
            _planner_system_prompt(),
            text,
            conversation_context,
            tool_results,
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
    plan = ActionPlan(
        actions=actions,
        confidence=float(payload.get("confidence") or 0),
    )
    logger.info("Planner raw response: %s", truncate_for_log(response.output_text))
    logger.info("Planner plan: %s", action_plan_for_log(plan))
    return plan


def _planner_system_prompt() -> str:
    now = datetime.now(ZoneInfo(settings.app_timezone))
    return (
        load_context_template("planner.md")
        .replace("{current_date}", now.date().isoformat())
        .replace("{timezone}", settings.app_timezone)
    )


async def assistant_chat(text: str, conversation_context: list[ConversationMessage] | None = None) -> str:
    logger.info(
        "Assistant fallback starting: model=%s reasoning_effort=%s text=%s conversation_messages=%s",
        settings.executioner_model,
        settings.executioner_reasoning_effort,
        truncate_for_log(text),
        len(conversation_context or []),
    )
    if not settings.openai_api_key:
        return "I can route commands, but OPENAI_API_KEY is not configured yet."

    response = await create_response(
        api_key=settings.openai_api_key,
        model=settings.executioner_model,
        reasoning_effort=settings.executioner_reasoning_effort,
        input=_llm_input(
            "You are DOBBY, Mark's personal assistant. Be concise and useful in Telegram.",
            text,
            conversation_context,
        ),
    )
    final = response.output_text.strip()
    logger.info("Assistant fallback result: %s", truncate_for_log(final))
    return final
