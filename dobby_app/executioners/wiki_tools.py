from __future__ import annotations

from typing import Any

from dobby_app.assistant.execution_results import ToolExecutionResult, ToolStatus
from dobby_app.executioners.common import schema
from dobby_app.memory.wiki_service import wiki_service


def obsidian_health() -> Any:
    return wiki_service.health()


def obsidian_list(path: str | None = None) -> Any:
    return wiki_service.list(path)


def obsidian_search_simple(query: str) -> Any:
    return wiki_service.search_simple(query)


def obsidian_search_structured(jsonlogic: dict[str, Any]) -> Any:
    return wiki_service.search_structured(jsonlogic)


def obsidian_read(
    path: str,
    target_type: str | None = None,
    target: str | None = None,
) -> str:
    return wiki_service.read(path, target_type=target_type, target=target)


def obsidian_document_map(path: str) -> Any:
    return wiki_service.document_map(path)


def obsidian_tags() -> Any:
    return wiki_service.tags()


def obsidian_active_file_path() -> str:
    return wiki_service.active_file_path()


def obsidian_open_file(path: str) -> Any:
    return wiki_service.open_file(path)


def obsidian_write(path: str | None = None, content: str | None = None) -> ToolExecutionResult:
    if not path or content is None:
        return ToolExecutionResult(
            tool="wiki",
            operation="write",
            status=ToolStatus.NEEDS_CLARIFICATION,
            message="Which wiki path and content should I write?",
        )
    message = wiki_service.write(path, content)
    return ToolExecutionResult(
        tool="wiki",
        operation="write",
        status=ToolStatus.SUCCESS,
        message=message or f"Wrote wiki file: {path}.",
        data={"path": path},
    )


def obsidian_append(
    path: str | None = None,
    content: str | None = None,
    target_type: str | None = None,
    target: str | None = None,
) -> ToolExecutionResult:
    if not path or content is None:
        return ToolExecutionResult(
            tool="wiki",
            operation="append",
            status=ToolStatus.NEEDS_CLARIFICATION,
            message="Which wiki path and content should I append?",
        )
    message = wiki_service.append(path, content, target_type=target_type, target=target)
    return ToolExecutionResult(
        tool="wiki",
        operation="append",
        status=ToolStatus.SUCCESS,
        message=message or f"Appended to wiki file: {path}.",
        data={"path": path, "target_type": target_type, "target": target},
    )


def obsidian_patch(
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
            status=ToolStatus.NEEDS_CLARIFICATION,
            message="Which wiki path, target, patch operation, and content should I apply?",
        )
    message = wiki_service.patch(
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
        status=ToolStatus.SUCCESS,
        message=message or f"Patched wiki file: {path}.",
        data={"path": path, "operation": operation, "target_type": target_type, "target": target},
    )


def obsidian_delete(path: str | None = None) -> ToolExecutionResult:
    if not path:
        return ToolExecutionResult(
            tool="wiki",
            operation="delete",
            status=ToolStatus.NEEDS_CLARIFICATION,
            message="Which wiki path should I delete?",
        )
    message = wiki_service.delete(path)
    return ToolExecutionResult(
        tool="wiki",
        operation="delete",
        status=ToolStatus.SUCCESS,
        message=message or f"Deleted wiki file: {path}.",
        data={"path": path},
    )


def require_obsidian() -> None:
    wiki_service.require_enabled()


def obsidian_health_schema() -> dict:
    return schema(
        "obsidian_health",
        "Check whether the Obsidian Local REST API is reachable and authenticated. Returns the API health payload.",
        {},
        [],
    )


def obsidian_list_schema() -> dict:
    return schema(
        "obsidian_list",
        (
            "List vault files/directories under `path`. Use an empty string or null to list the vault root. "
            "Returns the Obsidian Local REST API directory listing payload."
        ),
        {"path": {"type": ["string", "null"]}},
        ["path"],
    )


def obsidian_search_simple_schema() -> dict:
    return schema(
        "obsidian_search_simple",
        "Search the Obsidian vault with Obsidian's built-in full-text search.",
        {"query": {"type": "string"}},
        ["query"],
    )


def obsidian_search_structured_schema() -> dict:
    return schema(
        "obsidian_search_structured",
        "Search the Obsidian vault with a JsonLogic query against metadata.",
        {"jsonlogic": {"type": "object"}},
        ["jsonlogic"],
    )


def obsidian_read_schema() -> dict:
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


def obsidian_document_map_schema() -> dict:
    return schema(
        "obsidian_document_map",
        "Return headings, block references, and frontmatter fields for a note.",
        {"path": {"type": "string"}},
        ["path"],
    )


def obsidian_tags_schema() -> dict:
    return schema(
        "obsidian_tags",
        "List all tags across the Obsidian vault with usage counts.",
        {},
        [],
    )


def obsidian_active_file_path_schema() -> dict:
    return schema(
        "obsidian_active_file_path",
        "Return the vault-relative path of the active file in the Obsidian UI.",
        {},
        [],
    )


def obsidian_open_file_schema() -> dict:
    return schema(
        "obsidian_open_file",
        "Open a vault-relative file path in the Obsidian UI and return the API response.",
        {"path": {"type": "string"}},
        ["path"],
    )


def obsidian_write_schema() -> dict:
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


def obsidian_append_schema() -> dict:
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


def obsidian_patch_schema() -> dict:
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


def obsidian_delete_schema() -> dict:
    return schema(
        "obsidian_delete",
        "Delete one vault-relative file from Obsidian. This removes the whole file at `path`.",
        {"path": {"type": ["string", "null"]}},
        ["path"],
    )
