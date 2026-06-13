from __future__ import annotations

from dobby_app.execution_results import ToolExecutionResult
from dobby_app.executioner_agent import ExecutionTool, run_executioner_agent
from dobby_app.executioners.calendar_tools import (
    calendar_create,
    calendar_create_schema,
    calendar_delete,
    calendar_delete_schema,
    calendar_read_range,
    calendar_read_schema,
    calendar_update,
    calendar_update_schema,
)
from dobby_app.executioners.common import needs_clarification_schema
from dobby_app.router import ConversationMessage, PlannedAction


async def execute_calendar_action(
    action: PlannedAction,
    latest_text: str,
    conversation_context: list[ConversationMessage] | None = None,
) -> ToolExecutionResult:
    operation = action.operation or "read"
    return await run_executioner_agent(
        executor_name="calendar",
        context_template="tools/calendar.md",
        action=action,
        latest_text=latest_text,
        conversation_context=conversation_context,
        tools=[
            ExecutionTool(schema=calendar_read_schema(), handler=calendar_read_range, terminal=True),
            ExecutionTool(schema=calendar_create_schema(), handler=calendar_create, terminal=True),
            ExecutionTool(schema=calendar_update_schema(), handler=calendar_update, terminal=True),
            ExecutionTool(schema=calendar_delete_schema(), handler=calendar_delete, terminal=True),
            ExecutionTool(
                schema=needs_clarification_schema(),
                handler=lambda message: ToolExecutionResult(
                    tool="calendar",
                    operation=operation,
                    status="needs_clarification",
                    message=message,
                ),
                terminal=True,
            ),
        ],
    )
