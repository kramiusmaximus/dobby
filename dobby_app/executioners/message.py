from __future__ import annotations

from dobby_app.execution_results import ToolExecutionResult, ToolStatus
from dobby_app.executioner_agent import ExecutionTool, run_executioner_agent
from dobby_app.executioners.common import needs_clarification_schema, schema
from dobby_app.router import ConversationMessage, PlannedAction


def _send_result(content: str) -> ToolExecutionResult:
    return ToolExecutionResult(
        tool="message",
        operation="send",
        status=ToolStatus.SUCCESS,
        message=content,
    )


def _react_result(emoji: str) -> ToolExecutionResult:
    return ToolExecutionResult(
        tool="message",
        operation="react",
        status=ToolStatus.SUCCESS,
        message=None,
        data={"reaction_emoji": emoji},
    )


async def execute_message_action(
    action: PlannedAction,
    latest_text: str,
    conversation_context: list[ConversationMessage] | None = None,
) -> ToolExecutionResult:
    return await run_executioner_agent(
        executor_name="message",
        context_template="tools/message.md",
        action=action,
        latest_text=latest_text,
        conversation_context=conversation_context,
        tools=[
            *message_execution_tools(),
            ExecutionTool(
                schema=needs_clarification_schema(),
                handler=lambda message: ToolExecutionResult(
                    tool="message",
                    operation=action.operation,
                    status=ToolStatus.NEEDS_CLARIFICATION,
                    message=message,
                ),
                terminal=True,
            ),
        ],
    )


def message_execution_tools() -> list[ExecutionTool]:
    return [
        ExecutionTool(schema=schema_factory(), handler=handler, terminal=terminal)
        for schema_factory, handler, terminal in MESSAGE_TOOL_DEFINITIONS
    ]


def _message_send_schema() -> dict:
    return schema(
        "message_send",
        "Send final Telegram text to Mark.",
        {"content": {"type": "string"}},
        ["content"],
    )


def _message_react_schema() -> dict:
    return schema(
        "message_react",
        (
            "React to Mark's latest Telegram message with exactly one emoji instead of sending a text reply. "
            "Use this only for lightweight acknowledgements where no text response is needed. The emoji must be "
            "a Telegram reaction emoji such as 👍, 👀, ❤️, 🔥, 🎉, or ✅."
        ),
        {"emoji": {"type": "string"}},
        ["emoji"],
    )


MESSAGE_TOOL_DEFINITIONS = (
    (_message_send_schema, _send_result, True),
    (_message_react_schema, _react_result, True),
)
