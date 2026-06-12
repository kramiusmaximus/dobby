from __future__ import annotations

from typing import Any


def schema(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "required": required,
        },
    }


def needs_clarification_schema() -> dict[str, Any]:
    return schema(
        "needs_clarification",
        "Stop execution and ask Mark a concise clarification question.",
        {"message": {"type": "string"}},
        ["message"],
    )
