from __future__ import annotations

import json
from typing import Any

MAX_LOG_CHARS = 4000


def reasoning(effort: str) -> dict[str, str]:
    return {"effort": effort}


def truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n[truncated]"


def truncate_for_log(value: str, max_chars: int = MAX_LOG_CHARS) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "...[truncated]"


def planned_action_for_log(action: Any) -> str:
    return truncate_for_log(
        json.dumps(
            {
                "tool": action.tool,
                "operation": action.operation,
                "reason": action.reason,
                "arguments": action.arguments,
            },
            ensure_ascii=False,
            default=str,
        )
    )


def action_plan_for_log(plan: Any) -> str:
    return truncate_for_log(
        json.dumps(
            {
                "confidence": plan.confidence,
                "actions": [
                    {
                        "tool": action.tool,
                        "operation": action.operation,
                        "reason": action.reason,
                        "arguments": action.arguments,
                    }
                    for action in plan.actions
                ],
            },
            ensure_ascii=False,
            default=str,
        )
    )


def tool_execution_result_payload(result: Any) -> dict[str, Any]:
    return {
        "tool": result.tool,
        "operation": result.operation,
        "status": result.status,
        "message": result.message,
        "data": result.data,
    }


def result_for_log(result: Any) -> str:
    payload = tool_execution_result_payload(result) if _looks_like_tool_result(result) else result
    return truncate_for_log(json.dumps(payload, ensure_ascii=False, default=str))


def tool_call_for_log(call: dict[str, Any]) -> dict[str, Any]:
    return {
        "call_id": call.get("call_id"),
        "name": call.get("name"),
        "arguments": truncate_for_log(call.get("arguments") or ""),
    }


def _looks_like_tool_result(result: Any) -> bool:
    return all(hasattr(result, name) for name in ("tool", "operation", "status", "message", "data"))
