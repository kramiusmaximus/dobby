from __future__ import annotations

from dataclasses import dataclass

from dobby_app.assistant.execution_results import ToolExecutionResult, ToolStatus
from dobby_app.assistant.llm_logging import tool_execution_result_payload
from dobby_app.assistant.router import ActionPlan, PlannedTask, assistant_chat, plan_actions
from dobby_app.assistant.tool_dispatch import execute_tool_action

MAX_PLANNER_TOOL_ROUNDS = 3


@dataclass(frozen=True)
class HandlerResponse:
    text: str | None = None
    reaction_emoji: str | None = None


@dataclass(frozen=True)
class TaskHandlerResponse:
    source_message_ids: list[int]
    text: str | None = None
    reaction_emoji: str | None = None


async def handle_plain_text_result(
    text: str,
    conversation_context: list[dict[str, str]] | None = None,
) -> HandlerResponse:
    plan = await plan_actions(text, conversation_context)
    if plan.confidence < 0.35:
        return HandlerResponse(text=await assistant_chat(text, conversation_context))
    return await execute_action_plan_result(plan, text, conversation_context)


async def execute_action_plan_result(
    plan: ActionPlan,
    text: str,
    conversation_context: list[dict[str, str]] | None = None,
) -> HandlerResponse:
    task_responses = await execute_action_plan_task_results(plan, text, conversation_context)
    text_outputs = [response.text for response in task_responses if response.text]
    if text_outputs:
        return HandlerResponse(text="\n\n".join(text_outputs))
    reaction_outputs = [response.reaction_emoji for response in task_responses if response.reaction_emoji]
    if reaction_outputs:
        return HandlerResponse(reaction_emoji=reaction_outputs[-1])
    return HandlerResponse(text=await assistant_chat(text, conversation_context))


async def execute_action_plan_task_results(
    plan: ActionPlan,
    text: str,
    conversation_context: list[dict[str, str]] | None = None,
) -> list[TaskHandlerResponse]:
    responses: list[TaskHandlerResponse] = []
    for task in plan.tasks:
        responses.append(await execute_task_result(task, text, conversation_context))
    return responses


async def execute_task_result(
    task: PlannedTask,
    text: str,
    conversation_context: list[dict[str, str]] | None = None,
) -> TaskHandlerResponse:
    current_task = task
    all_results: list[ToolExecutionResult] = []
    for _round in range(MAX_PLANNER_TOOL_ROUNDS):
        results = await execute_task_once(current_task, text, conversation_context)
        all_results.extend(results)
        message_outputs = [
            result.message
            for result in results
            if result.tool == "message" and result.status == ToolStatus.SUCCESS and result.message
        ]
        if message_outputs:
            return TaskHandlerResponse(
                source_message_ids=current_task.source_message_ids,
                text="\n\n".join(message_outputs),
            )

        reaction_outputs = [
            str(result.data["reaction_emoji"])
            for result in results
            if result.tool == "message"
            and result.status == ToolStatus.SUCCESS
            and result.data.get("reaction_emoji")
        ]
        if reaction_outputs:
            return TaskHandlerResponse(
                source_message_ids=current_task.source_message_ids,
                reaction_emoji=reaction_outputs[-1],
            )

        if not planner_should_continue(results):
            non_message_outputs = [
                result.message for result in results if result.message and result.status != ToolStatus.SUCCESS
            ]
            if non_message_outputs:
                return TaskHandlerResponse(
                    source_message_ids=current_task.source_message_ids,
                    text="\n\n".join(non_message_outputs),
                )
            break

        next_plan = await plan_actions(
            text,
            conversation_context,
            tool_results=[tool_execution_result_payload(result) for result in all_results],
        )
        next_task = next_plan.tasks[0]
        if not next_task.source_message_ids:
            next_task = PlannedTask(
                source_message_ids=current_task.source_message_ids,
                actions=next_task.actions,
                reason=next_task.reason,
            )
        current_task = next_task

    return TaskHandlerResponse(
        source_message_ids=current_task.source_message_ids,
        text=await assistant_chat(text, conversation_context),
    )


async def execute_plan_once(
    plan: ActionPlan,
    text: str,
    conversation_context: list[dict[str, str]] | None = None,
) -> list[ToolExecutionResult]:
    results: list[ToolExecutionResult] = []
    for task in plan.tasks:
        results.extend(await execute_task_once(task, text, conversation_context))
    return results


async def execute_task_once(
    task: PlannedTask,
    text: str,
    conversation_context: list[dict[str, str]] | None = None,
) -> list[ToolExecutionResult]:
    results = []
    for action in task.actions:
        try:
            results.append(await execute_tool_action(action, text, conversation_context))
        except Exception as exc:
            results.append(
                ToolExecutionResult(
                    tool=action.tool,
                    operation=action.operation,
                    status=ToolStatus.FAILED,
                    message=f"I could not complete that: {exc}",
                )
            )
    return results


def planner_should_continue(results: list[ToolExecutionResult]) -> bool:
    if any(result.tool == "message" and result.status == ToolStatus.SUCCESS for result in results):
        return False
    return any(result.tool != "message" for result in results)
