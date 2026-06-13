from __future__ import annotations

import logging

from dobby_app.assistant.execution_results import ToolExecutionResult, ToolStatus
from dobby_app.executioners.calendar import execute_calendar_action
from dobby_app.executioners.message import execute_message_action
from dobby_app.executioners.wiki import execute_wiki_action
from dobby_app.assistant.llm_logging import planned_action_for_log, result_for_log, truncate_for_log
from dobby_app.assistant.router import ConversationMessage, PlannedAction

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
    if action.tool == "wiki":
        result = await execute_wiki_action(action, latest_text, conversation_context)
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
