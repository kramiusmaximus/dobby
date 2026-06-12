from __future__ import annotations

from typing import Any

from dobby_app.execution_results import ToolExecutionResult
from dobby_app.executioner_agent import ExecutionTool, run_executioner_agent
from dobby_app.executioners.common import needs_clarification_schema, schema
from dobby_app.obsidian_client import get_obsidian_client, obsidian_is_enabled
from dobby_app.router import ConversationMessage, PlannedAction


async def execute_wiki_action(
    action: PlannedAction,
    latest_text: str,
    conversation_context: list[ConversationMessage] | None = None,
) -> ToolExecutionResult:
    return await run_executioner_agent(
        executor_name="wiki",
        context_template="tools/wiki.md",
        action=action,
        latest_text=latest_text,
        conversation_context=conversation_context,
        tools=[
            ExecutionTool(schema=_obsidian_list_schema(), handler=_obsidian_list),
            ExecutionTool(schema=_obsidian_search_simple_schema(), handler=_obsidian_search_simple),
            ExecutionTool(schema=_obsidian_search_structured_schema(), handler=_obsidian_search_structured),
            ExecutionTool(schema=_obsidian_read_schema(), handler=_obsidian_read),
            ExecutionTool(schema=_obsidian_document_map_schema(), handler=_obsidian_document_map),
            ExecutionTool(schema=_obsidian_tags_schema(), handler=_obsidian_tags),
            ExecutionTool(schema=_obsidian_health_schema(), handler=_obsidian_health),
            ExecutionTool(schema=_obsidian_active_file_path_schema(), handler=_obsidian_active_file_path),
            ExecutionTool(schema=_obsidian_open_file_schema(), handler=_obsidian_open_file),
            ExecutionTool(schema=_obsidian_write_schema(), handler=_obsidian_write, terminal=True),
            ExecutionTool(schema=_obsidian_append_schema(), handler=_obsidian_append, terminal=True),
            ExecutionTool(schema=_obsidian_patch_schema(), handler=_obsidian_patch, terminal=True),
            ExecutionTool(schema=_obsidian_delete_schema(), handler=_obsidian_delete, terminal=True),
            ExecutionTool(
                schema=needs_clarification_schema(),
                handler=lambda message: ToolExecutionResult(
                    tool="wiki",
                    operation=action.operation,
                    status="needs_clarification",
                    message=message,
                ),
                terminal=True,
            ),
        ],
    )


def _obsidian_health() -> Any:
    _require_obsidian()
    return get_obsidian_client().health()


def _obsidian_list(path: str | None = None) -> Any:
    _require_obsidian()
    return get_obsidian_client().list(path or "")


def _obsidian_search_simple(query: str) -> Any:
    _require_obsidian()
    return get_obsidian_client().search_simple(query)


def _obsidian_search_structured(jsonlogic: dict[str, Any]) -> Any:
    _require_obsidian()
    return get_obsidian_client().search_structured(jsonlogic)


def _obsidian_read(
    path: str,
    target_type: str | None = None,
    target: str | None = None,
) -> str:
    _require_obsidian()
    return get_obsidian_client().read(path, target_type=target_type, target=target)


def _obsidian_document_map(path: str) -> Any:
    _require_obsidian()
    return get_obsidian_client().document_map(path)


def _obsidian_tags() -> Any:
    _require_obsidian()
    return get_obsidian_client().tags()


def _obsidian_active_file_path() -> str:
    _require_obsidian()
    return get_obsidian_client().active_file_path()


def _obsidian_open_file(path: str) -> Any:
    _require_obsidian()
    return get_obsidian_client().open_file(path)


def _obsidian_write(path: str | None = None, content: str | None = None) -> ToolExecutionResult:
    if not path or content is None:
        return ToolExecutionResult(
            tool="wiki",
            operation="write",
            status="needs_clarification",
            message="Which wiki path and content should I write?",
        )
    _require_obsidian()
    message = get_obsidian_client().write(path, content)
    return ToolExecutionResult(
        tool="wiki",
        operation="write",
        status="success",
        message=message or f"Wrote wiki file: {path}.",
        data={"path": path},
    )


def _obsidian_append(
    path: str | None = None,
    content: str | None = None,
    target_type: str | None = None,
    target: str | None = None,
) -> ToolExecutionResult:
    if not path or content is None:
        return ToolExecutionResult(
            tool="wiki",
            operation="append",
            status="needs_clarification",
            message="Which wiki path and content should I append?",
        )
    _require_obsidian()
    message = get_obsidian_client().append(path, content, target_type=target_type, target=target)
    return ToolExecutionResult(
        tool="wiki",
        operation="append",
        status="success",
        message=message or f"Appended to wiki file: {path}.",
        data={"path": path, "target_type": target_type, "target": target},
    )


def _obsidian_patch(
    path: str | None = None,
    content: str | None = None,
    operation: str | None = None,
    target_type: str | None = None,
    target: str | None = None,
    content_type: str | None = None,
) -> ToolExecutionResult:
    if not path or content is None or not operation or not target_type or not target:
        return ToolExecutionResult(
            tool="wiki",
            operation="patch",
            status="needs_clarification",
            message="Which wiki path, target, patch operation, and content should I apply?",
        )
    _require_obsidian()
    message = get_obsidian_client().patch(
        path,
        content,
        operation=operation,
        target_type=target_type,
        target=target,
        content_type=content_type or "text/plain",
    )
    return ToolExecutionResult(
        tool="wiki",
        operation="patch",
        status="success",
        message=message or f"Patched wiki file: {path}.",
        data={"path": path, "operation": operation, "target_type": target_type, "target": target},
    )


def _obsidian_delete(path: str | None = None) -> ToolExecutionResult:
    if not path:
        return ToolExecutionResult(
            tool="wiki",
            operation="delete",
            status="needs_clarification",
            message="Which wiki path should I delete?",
        )
    _require_obsidian()
    message = get_obsidian_client().delete(path)
    return ToolExecutionResult(
        tool="wiki",
        operation="delete",
        status="success",
        message=message or f"Deleted wiki file: {path}.",
        data={"path": path},
    )


def _require_obsidian() -> None:
    if not obsidian_is_enabled():
        raise RuntimeError("Obsidian API is not configured, so DOBBY memory queries are unavailable.")


def _obsidian_health_schema() -> dict:
    return schema(
        "obsidian_health",
        "Check whether the Obsidian Local REST API is reachable and authenticated. Returns the API health payload.",
        {},
        [],
    )


def _obsidian_list_schema() -> dict:
    return schema(
        "obsidian_list",
        (
            "List vault files/directories under `path`. Use an empty string or null to list the vault root. "
            "Returns the Obsidian Local REST API directory listing payload."
        ),
        {"path": {"type": ["string", "null"]}},
        ["path"],
    )


def _obsidian_search_simple_schema() -> dict:
    return schema(
        "obsidian_search_simple",
        "Search the Obsidian vault with Obsidian's built-in full-text search.",
        {"query": {"type": "string"}},
        ["query"],
    )


def _obsidian_search_structured_schema() -> dict:
    return schema(
        "obsidian_search_structured",
        "Search the Obsidian vault with a JsonLogic query against metadata.",
        {"jsonlogic": {"type": "object"}},
        ["jsonlogic"],
    )


def _obsidian_read_schema() -> dict:
    return schema(
        "obsidian_read",
        (
            "Read a note or targeted section by vault-relative path. `target_type` and `target` are optional "
            "Obsidian Local REST target headers. Use both as null to read the full file. For targeted reads, provide "
            "both fields, for example target_type='heading' with target='Calendar Sync'."
        ),
        {
            "path": {"type": "string"},
            "target_type": {"type": ["string", "null"]},
            "target": {"type": ["string", "null"]},
        },
        ["path", "target_type", "target"],
    )


def _obsidian_document_map_schema() -> dict:
    return schema(
        "obsidian_document_map",
        "Return headings, block references, and frontmatter fields for a note.",
        {"path": {"type": "string"}},
        ["path"],
    )


def _obsidian_tags_schema() -> dict:
    return schema(
        "obsidian_tags",
        "List all tags across the Obsidian vault with usage counts.",
        {},
        [],
    )


def _obsidian_active_file_path_schema() -> dict:
    return schema(
        "obsidian_active_file_path",
        "Return the vault-relative path of the active file in the Obsidian UI.",
        {},
        [],
    )


def _obsidian_open_file_schema() -> dict:
    return schema(
        "obsidian_open_file",
        "Open a vault-relative file path in the Obsidian UI and return the API response.",
        {"path": {"type": "string"}},
        ["path"],
    )


def _obsidian_write_schema() -> dict:
    return schema(
        "obsidian_write",
        (
            "Replace the complete contents of one vault-relative file. This is a raw full-file write: include the "
            "entire desired Markdown/file content, including frontmatter when needed. Use only when you intend to "
            "overwrite the whole file."
        ),
        {
            "path": {"type": ["string", "null"]},
            "content": {"type": ["string", "null"]},
        },
        ["path", "content"],
    )


def _obsidian_append_schema() -> dict:
    return schema(
        "obsidian_append",
        (
            "Append raw text to a vault-relative file. If `target_type` and `target` are null, append to the end of "
            "the file. If both are provided, Obsidian appends relative to that target, such as target_type='heading' "
            "and target='Inbox'."
        ),
        {
            "path": {"type": ["string", "null"]},
            "content": {"type": ["string", "null"]},
            "target_type": {"type": ["string", "null"]},
            "target": {"type": ["string", "null"]},
        },
        ["path", "content", "target_type", "target"],
    )


def _obsidian_patch_schema() -> dict:
    return schema(
        "obsidian_patch",
        (
            "Patch a vault-relative file through Obsidian Local REST. Requires `operation`, `target_type`, and "
            "`target`, which are sent as Obsidian patch headers. `content_type` defaults to text/plain when null; "
            "use application/json for frontmatter JSON values."
        ),
        {
            "path": {"type": ["string", "null"]},
            "content": {"type": ["string", "null"]},
            "operation": {"type": ["string", "null"]},
            "target_type": {"type": ["string", "null"]},
            "target": {"type": ["string", "null"]},
            "content_type": {"type": ["string", "null"]},
        },
        ["path", "content", "operation", "target_type", "target", "content_type"],
    )


def _obsidian_delete_schema() -> dict:
    return schema(
        "obsidian_delete",
        "Delete one vault-relative file from Obsidian. This removes the whole file at `path`.",
        {"path": {"type": ["string", "null"]}},
        ["path"],
    )
