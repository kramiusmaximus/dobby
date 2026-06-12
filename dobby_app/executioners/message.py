from __future__ import annotations

from dobby_app.execution_results import ToolExecutionResult
from dobby_app.executioner_agent import ExecutionTool, run_executioner_agent
from dobby_app.executioners.common import needs_clarification_schema, schema
from dobby_app.router import ConversationMessage, PlannedAction


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
            ExecutionTool(
                schema=_message_send_schema(),
                handler=lambda content: ToolExecutionResult(
                    tool="message",
                    operation="send",
                    status="success",
                    message=content,
                ),
                terminal=True,
            ),
            ExecutionTool(
                schema=_message_react_schema(),
                handler=lambda emoji: ToolExecutionResult(
                    tool="message",
                    operation="react",
                    status="success",
                    message=None,
                    data={"reaction_emoji": emoji},
                ),
                terminal=True,
            ),
            ExecutionTool(
                schema=needs_clarification_schema(),
                handler=lambda message: ToolExecutionResult(
                    tool="message",
                    operation=action.operation,
                    status="needs_clarification",
                    message=message,
                ),
                terminal=True,
            ),
        ],
    )


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
