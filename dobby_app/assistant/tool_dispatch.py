from __future__ import annotations

import logging

from dobby_app.assistant.execution_results import ToolExecutionResult, ToolStatus
from dobby_app.assistant.tools.calendar_reminders import execute_calendar_action
from dobby_app.assistant.tools.jobs import execute_jobs_action
from dobby_app.assistant.tools.memory import execute_memory_action
from dobby_app.assistant.tools.messaging import execute_message_action
from dobby_app.assistant.llm_logging import planned_action_for_log, result_for_log, truncate_for_log
from dobby_app.assistant.router import ConversationMessage, PlannedAction
from dobby_app.commands import handle_command
from dobby_app.db.session import session_scope

logger = logging.getLogger(__name__)


async def execute_tool_action(
    action: PlannedAction,
    latest_text: str,
    conversation_context: list[ConversationMessage] | None = None,
) -> ToolExecutionResult:
    logger.info(
        "Dispatching executor action: action=%s conversation_messages=%s latest_text=%s",
        planned_action_for_log(action),
        len(conversation_context or []),
        truncate_for_log(latest_text),
    )
    if action.tool == "message":
        result = await execute_message_action(action, latest_text, conversation_context)
        logger.info("Executor action completed: result=%s", result_for_log(result))
        return result
    if action.tool == "calendar":
        result = await execute_calendar_action(action, latest_text, conversation_context)
        logger.info("Executor action completed: result=%s", result_for_log(result))
        return result
    if action.tool == "memory":
        result = await execute_memory_action(action, latest_text, conversation_context)
        logger.info("Executor action completed: result=%s", result_for_log(result))
        return result
    if action.tool == "jobs":
        result = await execute_jobs_action(action, latest_text, conversation_context)
        logger.info("Executor action completed: result=%s", result_for_log(result))
        return result
    if action.tool == "command":
        command_text = (action.arguments.get("command") or latest_text or "").strip()
        if not command_text:
            result = ToolExecutionResult(
                tool="command",
                operation=action.operation or "execute",
                status=ToolStatus.NEEDS_CLARIFICATION,
                message="Which command should I run?",
            )
            logger.info("Executor action needs clarification: result=%s", result_for_log(result))
            return result
        with session_scope() as session:
            message = handle_command(session, command_text)
        result = ToolExecutionResult(
            tool="command",
            operation=action.operation or "execute",
            status=ToolStatus.SUCCESS,
            message=message,
            data={"command": command_text},
        )
        logger.info("Executor action completed: result=%s", result_for_log(result))
        return result
    result = ToolExecutionResult(
        tool=action.tool,
        operation=action.operation,
        status=ToolStatus.UNSUPPORTED,
        message=f"Unsupported tool: {action.tool}",
    )
    logger.info("Executor action unsupported: result=%s", result_for_log(result))
    return result
