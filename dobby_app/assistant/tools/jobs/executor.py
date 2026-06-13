from __future__ import annotations

from dobby_app.assistant.execution_results import ToolExecutionResult, ToolStatus
from dobby_app.assistant.executioner_agent import ExecutionTool, run_executioner_agent
from dobby_app.assistant.tools.common import needs_clarification_schema
from dobby_app.assistant.tools.jobs.functions import (
    jobs_create,
    jobs_create_schema,
    jobs_delete,
    jobs_delete_schema,
    jobs_list,
    jobs_list_schema,
    jobs_pause,
    jobs_pause_schema,
    jobs_resume,
    jobs_resume_schema,
    jobs_run,
    jobs_run_schema,
    jobs_show,
    jobs_show_schema,
    jobs_update,
    jobs_update_schema,
)
from dobby_app.assistant.router import ConversationMessage, PlannedAction


JOBS_TOOL_DEFINITIONS = (
    (jobs_list_schema, jobs_list, True),
    (jobs_show_schema, jobs_show, True),
    (jobs_create_schema, jobs_create, True),
    (jobs_update_schema, jobs_update, True),
    (jobs_delete_schema, jobs_delete, True),
    (jobs_run_schema, jobs_run, True),
    (jobs_pause_schema, jobs_pause, True),
    (jobs_resume_schema, jobs_resume, True),
)


async def execute_jobs_action(
    action: PlannedAction,
    latest_text: str,
    conversation_context: list[ConversationMessage] | None = None,
) -> ToolExecutionResult:
    operation = action.operation or "read"
    return await run_executioner_agent(
        executor_name="jobs",
        context_template="tools/jobs.md",
        action=action,
        latest_text=latest_text,
        conversation_context=conversation_context,
        tools=[
            *jobs_execution_tools(),
            ExecutionTool(
                schema=needs_clarification_schema(),
                handler=lambda message: ToolExecutionResult(
                    tool="jobs",
                    operation=operation,
                    status=ToolStatus.NEEDS_CLARIFICATION,
                    message=message,
                ),
                terminal=True,
            ),
        ],
    )


def jobs_execution_tools() -> list[ExecutionTool]:
    return [
        ExecutionTool(schema=schema_factory(), handler=handler, terminal=terminal)
        for schema_factory, handler, terminal in JOBS_TOOL_DEFINITIONS
    ]
