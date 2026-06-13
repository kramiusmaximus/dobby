from __future__ import annotations

import inspect
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from dobby_app.core.config import settings
from dobby_app.core.context_templates import load_context_template
from dobby_app.assistant.execution_results import ToolExecutionResult, ToolStatus
from dobby_app.assistant.llm_client import create_response
from dobby_app.assistant.llm_logging import (
    planned_action_for_log,
    result_for_log,
    tool_call_for_log,
    truncate,
    truncate_for_log,
)
from dobby_app.assistant.router import ConversationMessage, PlannedAction

MAX_TOOL_OUTPUT_CHARS = 12000
MAX_EXECUTIONER_TOOL_ROUNDS = 6
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionTool:
    schema: dict[str, Any]
    handler: Callable[..., Any]
    terminal: bool = False


async def run_executioner_agent(
    *,
    executor_name: str,
    context_template: str,
    action: PlannedAction,
    latest_text: str,
    conversation_context: list[ConversationMessage] | None,
    tools: list[ExecutionTool],
    max_tool_rounds: int = MAX_EXECUTIONER_TOOL_ROUNDS,
) -> ToolExecutionResult:
    tool_names = [tool.schema["name"] for tool in tools]
    logger.info(
        "Executioner starting: executor=%s model=%s reasoning_effort=%s action=%s tools=%s conversation_messages=%s latest_text=%s",
        executor_name,
        settings.executioner_model,
        settings.executioner_reasoning_effort,
        planned_action_for_log(action),
        tool_names,
        len(conversation_context or []),
        truncate_for_log(latest_text),
    )
    if not settings.openai_api_key:
        result = ToolExecutionResult(
            tool=action.tool,
            operation=action.operation,
            status=ToolStatus.FAILED,
            message="OPENAI_API_KEY is not configured, so executioner agents are unavailable.",
        )
        logger.info("Executioner unavailable: executor=%s result=%s", executor_name, result_for_log(result))
        return result

    tool_map = {tool.schema["name"]: tool for tool in tools}
    executioner_input = _executioner_input(executor_name, context_template, action, latest_text, conversation_context)
    logger.info(
        "Executioner input prepared: executor=%s input=%s",
        executor_name,
        truncate_for_log(json.dumps(executioner_input, ensure_ascii=False, default=str)),
    )
    response = await create_response(
        api_key=settings.openai_api_key,
        model=settings.executioner_model,
        reasoning_effort=settings.executioner_reasoning_effort,
        input=executioner_input,
        tools=[tool.schema for tool in tools],
    )

    for round_index in range(max_tool_rounds):
        tool_calls = _function_calls(response)
        logger.info(
            "Executioner round: executor=%s round=%s response_id=%s tool_calls=%s output_text=%s",
            executor_name,
            round_index + 1,
            getattr(response, "id", None),
            [tool_call_for_log(call) for call in tool_calls],
            truncate_for_log(getattr(response, "output_text", "") or ""),
        )
        if not tool_calls:
            final = response.output_text.strip()
            if final:
                result = ToolExecutionResult(
                    tool=action.tool,
                    operation=action.operation,
                    status=ToolStatus.SUCCESS,
                    message=final,
                )
                logger.info("Executioner final text result: executor=%s result=%s", executor_name, result_for_log(result))
                return result
            result = ToolExecutionResult(
                tool=action.tool,
                operation=action.operation,
                status=ToolStatus.FAILED,
                message="The executioner agent finished without a result.",
            )
            logger.info("Executioner empty result: executor=%s result=%s", executor_name, result_for_log(result))
            return result

        tool_outputs = []
        for call in tool_calls:
            wrapper = tool_map.get(call["name"])
            if wrapper is None:
                result = ToolExecutionResult(
                    tool=action.tool,
                    operation=action.operation,
                    status=ToolStatus.UNSUPPORTED,
                    message=f"Unsupported executioner tool: {call['name']}",
                )
            else:
                result = await _execute_wrapper(wrapper, call, action)
            logger.info(
                "Executioner tool result: executor=%s tool_call=%s terminal=%s result=%s",
                executor_name,
                tool_call_for_log(call),
                bool(wrapper and wrapper.terminal),
                result_for_log(result),
            )
            tool_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call["call_id"],
                    "output": _json_tool_output(_tool_payload(result)),
                }
            )
            if wrapper and wrapper.terminal:
                logger.info("Executioner terminal tool result: executor=%s result=%s", executor_name, result_for_log(result))
                return result

        response = await create_response(
            api_key=settings.openai_api_key,
            model=settings.executioner_model,
            reasoning_effort=settings.executioner_reasoning_effort,
            previous_response_id=response.id,
            input=tool_outputs,
            tools=[tool.schema for tool in tools],
        )

    final = response.output_text.strip()
    if final:
        result = ToolExecutionResult(
            tool=action.tool,
            operation=action.operation,
            status=ToolStatus.SUCCESS,
            message=final,
        )
        logger.info("Executioner final text after budget: executor=%s result=%s", executor_name, result_for_log(result))
        return result
    result = ToolExecutionResult(
        tool=action.tool,
        operation=action.operation,
        status=ToolStatus.FAILED,
        message="The executioner agent could not finish within the tool budget.",
    )
    logger.info("Executioner tool budget exhausted: executor=%s result=%s", executor_name, result_for_log(result))
    return result


def _executioner_input(
    executor_name: str,
    context_template: str,
    action: PlannedAction,
    latest_text: str,
    conversation_context: list[ConversationMessage] | None,
) -> list[ConversationMessage]:
    system_prompt = _executioner_system_prompt(executor_name, context_template)
    task_payload = {
        "latest_text": latest_text,
        "planner_action": asdict(action),
    }
    messages: list[ConversationMessage] = [{"role": "system", "content": system_prompt}]
    if conversation_context:
        messages.extend(conversation_context)
    messages.append(
        {
            "role": "user",
            "content": (
                "Execute this planner-assigned task using only your available tools.\n"
                f"{json.dumps(task_payload, ensure_ascii=False, default=str)}"
            ),
        }
    )
    return messages


def _executioner_system_prompt(executor_name: str, context_template: str) -> str:
    now = datetime.now(ZoneInfo(settings.app_timezone))
    return (
        f"You are DOBBY's {executor_name} executioner agent for Mark.\n"
        f"Current date: {now.date().isoformat()}\n"
        f"Timezone: {settings.app_timezone}\n\n"
        f"{load_context_template(context_template)}"
    )


async def _execute_wrapper(
    wrapper: ExecutionTool,
    call: dict[str, Any],
    action: PlannedAction,
) -> Any:
    try:
        args = json.loads(call.get("arguments") or "{}")
        logger.info(
            "Executioner executing wrapper: tool=%s args=%s",
            call.get("name"),
            truncate_for_log(json.dumps(args, ensure_ascii=False, default=str)),
        )
        result = wrapper.handler(**args)
        if inspect.isawaitable(result):
            result = await result
        return _coerce_result(result, action)
    except Exception as exc:
        result = ToolExecutionResult(
            tool=action.tool,
            operation=action.operation,
            status=ToolStatus.FAILED,
            message=str(exc),
        )
        logger.exception("Executioner wrapper failed: tool=%s result=%s", call.get("name"), result_for_log(result))
        return result


def _coerce_result(result: Any, action: PlannedAction) -> Any:
    if isinstance(result, ToolExecutionResult):
        return result
    return {"ok": True, "result": result, "tool": action.tool, "operation": action.operation}


def _function_calls(response: Any) -> list[dict[str, Any]]:
    calls = []
    for item in getattr(response, "output", []) or []:
        item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
        if item_type != "function_call":
            continue
        calls.append(
            {
                "call_id": getattr(item, "call_id", None) or item.get("call_id"),
                "name": getattr(item, "name", None) or item.get("name"),
                "arguments": getattr(item, "arguments", None) or item.get("arguments"),
            }
        )
    return calls


def _tool_payload(result: Any) -> dict[str, Any]:
    if isinstance(result, ToolExecutionResult):
        return {
            "ok": result.status == ToolStatus.SUCCESS,
            "terminal": True,
            "status": result.status,
            "message": result.message,
            "data": result.data,
        }
    return {"ok": True, "terminal": False, "result": result}


def _json_tool_output(payload: dict[str, Any]) -> str:
    return truncate(json.dumps(payload, ensure_ascii=False, default=str), MAX_TOOL_OUTPUT_CHARS)
