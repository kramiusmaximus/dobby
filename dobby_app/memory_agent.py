from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from dobby_app.config import settings
from dobby_app.obsidian_client import ObsidianError, get_obsidian_client, obsidian_is_enabled


MAX_TOOL_OUTPUT_CHARS = 12000
MAX_TOOL_ROUNDS = 6


OBSIDIAN_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "obsidian_search_simple",
        "description": "Search the Obsidian vault with Obsidian's built-in full-text search.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "obsidian_search_structured",
        "description": "Search the Obsidian vault with a JsonLogic query against metadata.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"jsonlogic": {"type": "object"}},
            "required": ["jsonlogic"],
        },
    },
    {
        "type": "function",
        "name": "obsidian_read",
        "description": "Read a note by vault-relative path, such as index.md or pages/projects/name.md.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "type": "function",
        "name": "obsidian_document_map",
        "description": "Return headings, block references, and frontmatter fields for a note.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "type": "function",
        "name": "obsidian_tags",
        "description": "List all tags across the Obsidian vault with usage counts.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
            "required": [],
        },
    },
]


async def answer_memory_query(query: str, *, max_tool_rounds: int = MAX_TOOL_ROUNDS) -> str:
    if not query.strip():
        return "What should I search memory for?"
    if not obsidian_is_enabled():
        return "Obsidian API is not configured, so DOBBY memory queries are unavailable."
    if not settings.openai_api_key:
        return "OPENAI_API_KEY is not configured, so the Obsidian-backed memory agent is unavailable."

    try:
        get_obsidian_client().health()
    except ObsidianError as exc:
        return f"Obsidian API is unavailable: {exc}"

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.responses.create(
        model=settings.assistant_model,
        input=[
            {"role": "system", "content": _memory_system_prompt()},
            {"role": "user", "content": query},
        ],
        tools=OBSIDIAN_TOOL_SCHEMAS,
    )

    for _round in range(max_tool_rounds):
        tool_calls = _function_calls(response)
        if not tool_calls:
            return response.output_text.strip()

        tool_outputs = []
        for call in tool_calls:
            output = _execute_tool_call(call)
            tool_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call["call_id"],
                    "output": output,
                }
            )

        response = await client.responses.create(
            model=settings.assistant_model,
            previous_response_id=response.id,
            input=tool_outputs,
            tools=OBSIDIAN_TOOL_SCHEMAS,
        )

    final = response.output_text.strip()
    if final:
        return final
    return "I searched the Obsidian vault but could not finish the memory query within the tool budget."


def obsidian_append(path: str, content: str, *, target_type: str | None = None, target: str | None = None) -> str:
    return get_obsidian_client().append(path, content, target_type=target_type, target=target)


def obsidian_patch(
    path: str,
    content: str,
    *,
    operation: str,
    target_type: str,
    target: str,
    content_type: str = "text/plain",
) -> str:
    return get_obsidian_client().patch(
        path,
        content,
        operation=operation,
        target_type=target_type,
        target=target,
        content_type=content_type,
    )


def obsidian_write(path: str, content: str) -> str:
    return get_obsidian_client().write(path, content)


def _execute_tool_call(call: dict[str, Any]) -> str:
    try:
        args = json.loads(call.get("arguments") or "{}")
        result = _run_obsidian_tool(call["name"], args)
        return _json_tool_output({"ok": True, "result": result})
    except Exception as exc:
        return _json_tool_output({"ok": False, "error": str(exc)})


def _run_obsidian_tool(name: str, args: dict[str, Any]) -> Any:
    client = get_obsidian_client()
    if name == "obsidian_search_simple":
        return client.search_simple(str(args["query"]))
    if name == "obsidian_search_structured":
        return client.search_structured(dict(args["jsonlogic"]))
    if name == "obsidian_read":
        return client.read(str(args["path"]))
    if name == "obsidian_document_map":
        return client.document_map(str(args["path"]))
    if name == "obsidian_tags":
        return client.tags()
    raise ValueError(f"Unknown Obsidian tool: {name}")


def _function_calls(response: Any) -> list[dict[str, Any]]:
    calls = []
    for item in getattr(response, "output", []) or []:
        item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
        if item_type != "function_call":
            continue
        calls.append(
            {
                "call_id": getattr(item, "call_id", None) or item.get("call_id"),
                "name": getattr(item, "name", None) or item.get("name"),
                "arguments": getattr(item, "arguments", None) or item.get("arguments"),
            }
        )
    return calls


def _memory_system_prompt() -> str:
    return (
        "You are DOBBY, Mark's personal life assistant. Answer Telegram memory questions "
        "using Obsidian as the source of truth.\n\n"
        "Obsidian interface:\n"
        "- Start by reading index.md unless the user asked for a very specific known path.\n"
        "- Chain searches and reads. Use search first for broad questions, then read the strongest pages.\n"
        "- Use document maps when you need headings/frontmatter before reading or patching.\n"
        "- Search compiled wiki pages; raw sources may be useful evidence but should not be edited.\n"
        "- Cite note paths when making factual claims from memory.\n"
        "- Do not invent personal facts. Say when the vault lacks enough evidence.\n"
        "- Keep Telegram answers concise and readable.\n\n"
        "DOBBY operating context from AGENTS.md:\n"
        f"{_read_agents_context()}"
    )


def _read_agents_context() -> str:
    path = Path(__file__).resolve().parents[1] / "AGENTS.md"
    if not path.exists():
        return "AGENTS.md was not found."
    return _truncate(path.read_text(encoding="utf-8", errors="ignore"), 16000)


def _json_tool_output(payload: dict[str, Any]) -> str:
    return _truncate(json.dumps(payload, ensure_ascii=False, default=str), MAX_TOOL_OUTPUT_CHARS)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n[truncated]"
