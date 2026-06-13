from __future__ import annotations

from dobby_app.assistant.execution_results import ToolExecutionResult, ToolStatus
from dobby_app.assistant.executioner_agent import ExecutionTool, run_executioner_agent
from dobby_app.assistant.tools.calendar_reminders.functions import (
    calendar_create,
    calendar_create_schema,
    calendar_delete,
    calendar_delete_schema,
    calendar_read_range,
    calendar_read_schema,
    calendar_update,
    calendar_update_schema,
)
from dobby_app.assistant.tools.common import needs_clarification_schema
from dobby_app.assistant.router import ConversationMessage, PlannedAction


CALENDAR_TOOL_DEFINITIONS = (
    (calendar_read_schema, calendar_read_range, True),
    (calendar_create_schema, calendar_create, True),
    (calendar_update_schema, calendar_update, True),
    (calendar_delete_schema, calendar_delete, True),
)


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
            *calendar_execution_tools(),
            ExecutionTool(
                schema=needs_clarification_schema(),
                handler=lambda message: ToolExecutionResult(
                    tool="calendar",
                    operation=operation,
                    status=ToolStatus.NEEDS_CLARIFICATION,
                    message=message,
                ),
                terminal=True,
            ),
        ],
    )


def calendar_execution_tools() -> list[ExecutionTool]:
    return [
        ExecutionTool(schema=schema_factory(), handler=handler, terminal=terminal)
        for schema_factory, handler, terminal in CALENDAR_TOOL_DEFINITIONS
    ]
