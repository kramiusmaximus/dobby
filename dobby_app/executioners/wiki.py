from __future__ import annotations

from dobby_app.execution_results import ToolExecutionResult
from dobby_app.executioner_agent import ExecutionTool, run_executioner_agent
from dobby_app.executioners.common import needs_clarification_schema
from dobby_app.executioners.wiki_tools import (
    obsidian_active_file_path,
    obsidian_active_file_path_schema,
    obsidian_append,
    obsidian_append_schema,
    obsidian_delete,
    obsidian_delete_schema,
    obsidian_document_map,
    obsidian_document_map_schema,
    obsidian_health,
    obsidian_health_schema,
    obsidian_list,
    obsidian_list_schema,
    obsidian_open_file,
    obsidian_open_file_schema,
    obsidian_patch,
    obsidian_patch_schema,
    obsidian_read,
    obsidian_read_schema,
    obsidian_search_simple,
    obsidian_search_simple_schema,
    obsidian_search_structured,
    obsidian_search_structured_schema,
    obsidian_tags,
    obsidian_tags_schema,
    obsidian_write,
    obsidian_write_schema,
)
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
            ExecutionTool(schema=obsidian_list_schema(), handler=obsidian_list),
            ExecutionTool(schema=obsidian_search_simple_schema(), handler=obsidian_search_simple),
            ExecutionTool(schema=obsidian_search_structured_schema(), handler=obsidian_search_structured),
            ExecutionTool(schema=obsidian_read_schema(), handler=obsidian_read),
            ExecutionTool(schema=obsidian_document_map_schema(), handler=obsidian_document_map),
            ExecutionTool(schema=obsidian_tags_schema(), handler=obsidian_tags),
            ExecutionTool(schema=obsidian_health_schema(), handler=obsidian_health),
            ExecutionTool(schema=obsidian_active_file_path_schema(), handler=obsidian_active_file_path),
            ExecutionTool(schema=obsidian_open_file_schema(), handler=obsidian_open_file),
            ExecutionTool(schema=obsidian_write_schema(), handler=obsidian_write, terminal=True),
            ExecutionTool(schema=obsidian_append_schema(), handler=obsidian_append, terminal=True),
            ExecutionTool(schema=obsidian_patch_schema(), handler=obsidian_patch, terminal=True),
            ExecutionTool(schema=obsidian_delete_schema(), handler=obsidian_delete, terminal=True),
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
