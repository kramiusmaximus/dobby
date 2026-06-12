from __future__ import annotations

import json
import logging

from dobby_app.execution_results import ToolExecutionResult
from dobby_app.executioners.calendar import execute_calendar_action
from dobby_app.executioners.message import execute_message_action
from dobby_app.executioners.wiki import execute_wiki_action
from dobby_app.router import ConversationMessage, PlannedAction

logger = logging.getLogger(__name__)


async def execute_tool_action(
    action: PlannedAction,
    latest_text: str,
    conversation_context: list[ConversationMessage] | None = None,
) -> ToolExecutionResult:
    logger.info(
        "Dispatching executor action: action=%s conversation_messages=%s latest_text=%s",
        _action_for_log(action),
        len(conversation_context or []),
        _truncate_for_log(latest_text),
    )
    if action.tool == "message":
        result = await execute_message_action(action, latest_text, conversation_context)
        logger.info("Executor action completed: result=%s", _result_for_log(result))
        return result
    if action.tool == "calendar":
        result = await execute_calendar_action(action, latest_text, conversation_context)
        logger.info("Executor action completed: result=%s", _result_for_log(result))
        return result
    if action.tool == "wiki":
        result = await execute_wiki_action(action, latest_text, conversation_context)
        logger.info("Executor action completed: result=%s", _result_for_log(result))
        return result
    result = ToolExecutionResult(
        tool=action.tool,
        operation=action.operation,
        status="unsupported",
        message=f"Unsupported tool: {action.tool}",
    )
    logger.info("Executor action unsupported: result=%s", _result_for_log(result))
    return result


def _action_for_log(action: PlannedAction) -> str:
    return _truncate_for_log(
        json.dumps(
            {
                "tool": action.tool,
                "operation": action.operation,
                "reason": action.reason,
                "arguments": action.arguments,
            },
            ensure_ascii=False,
            default=str,
        )
    )


def _result_for_log(result: ToolExecutionResult) -> str:
    return _truncate_for_log(
        json.dumps(
            {
                "tool": result.tool,
                "operation": result.operation,
                "status": result.status,
                "message": result.message,
                "data": result.data,
            },
            ensure_ascii=False,
            default=str,
        )
    )


def _truncate_for_log(value: str, max_chars: int = 4000) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "...[truncated]"
