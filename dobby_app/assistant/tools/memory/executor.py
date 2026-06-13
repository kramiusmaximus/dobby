from __future__ import annotations

from dobby_app.assistant.execution_results import ToolExecutionResult, ToolStatus
from dobby_app.assistant.executioner_agent import ExecutionTool, run_executioner_agent
from dobby_app.assistant.tools.common import needs_clarification_schema
from dobby_app.assistant.tools.memory.functions import (
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
from dobby_app.assistant.router import ConversationMessage, PlannedAction


MEMORY_TOOL_DEFINITIONS = (
    (obsidian_list_schema, obsidian_list, False),
    (obsidian_search_simple_schema, obsidian_search_simple, False),
    (obsidian_search_structured_schema, obsidian_search_structured, False),
    (obsidian_read_schema, obsidian_read, False),
    (obsidian_document_map_schema, obsidian_document_map, False),
    (obsidian_tags_schema, obsidian_tags, False),
    (obsidian_health_schema, obsidian_health, False),
    (obsidian_active_file_path_schema, obsidian_active_file_path, False),
    (obsidian_open_file_schema, obsidian_open_file, False),
    (obsidian_write_schema, obsidian_write, True),
    (obsidian_append_schema, obsidian_append, True),
    (obsidian_patch_schema, obsidian_patch, True),
    (obsidian_delete_schema, obsidian_delete, True),
)


async def execute_memory_action(
    action: PlannedAction,
    latest_text: str,
    conversation_context: list[ConversationMessage] | None = None,
) -> ToolExecutionResult:
    return await run_executioner_agent(
        executor_name="memory",
        context_template="tools/memory.md",
        action=action,
        latest_text=latest_text,
        conversation_context=conversation_context,
        tools=[
            *memory_execution_tools(),
            ExecutionTool(
                schema=needs_clarification_schema(),
                handler=lambda message: ToolExecutionResult(
                    tool="memory",
                    operation=action.operation,
                    status=ToolStatus.NEEDS_CLARIFICATION,
                    message=message,
                ),
                terminal=True,
            ),
        ],
    )


def memory_execution_tools() -> list[ExecutionTool]:
    return [
        ExecutionTool(schema=schema_factory(), handler=handler, terminal=terminal)
        for schema_factory, handler, terminal in MEMORY_TOOL_DEFINITIONS
    ]
