from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dobby_app.commands import upcoming
from dobby_app.context_templates import load_context_template
from dobby_app.db import session_scope
from dobby_app.memory_agent import answer_memory_query
from dobby_app.models import CaldavItem
from dobby_app.router import PlannedAction
from dobby_app.timeparse import parse_datetime
from dobby_app.wiki_memory import delete_wiki_line, save_memory_note, update_wiki_line


@dataclass(frozen=True)
class ToolExecutionResult:
    tool: str
    operation: str | None
    status: str
    message: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_context_message(self) -> str:
        parts = [
            f"tool={self.tool}",
            f"operation={self.operation or 'none'}",
            f"status={self.status}",
        ]
        if self.message:
            parts.append(f"message={self.message}")
        if self.data:
            parts.append(f"data={self.data}")
        return "; ".join(parts)


async def execute_tool_action(action: PlannedAction, latest_text: str) -> ToolExecutionResult:
    if action.tool == "message":
        return execute_message_action(action)
    if action.tool == "calendar":
        return execute_calendar_action(action)
    if action.tool == "wiki":
        return await execute_wiki_action(action, latest_text)
    return ToolExecutionResult(
        tool=action.tool,
        operation=action.operation,
        status="unsupported",
        message=f"Unsupported tool: {action.tool}",
    )


def execute_message_action(action: PlannedAction) -> ToolExecutionResult:
    _context = load_context_template("tools/message.md")
    args = action.arguments
    text = args.get("content") or args.get("query") or args.get("title")
    if not text:
        return ToolExecutionResult(
            tool=action.tool,
            operation=action.operation,
            status="needs_clarification",
            message="What should I say?",
        )
    return ToolExecutionResult(
        tool=action.tool,
        operation=action.operation,
        status="success",
        message=text,
    )


def execute_calendar_action(action: PlannedAction) -> ToolExecutionResult:
    _context = load_context_template("tools/calendar.md")
    operation = action.operation or "read"
    args = action.arguments

    if operation == "read":
        days = int(args.get("days") or 14)
        return ToolExecutionResult(
            tool=action.tool,
            operation=operation,
            status="success",
            message=upcoming(days=days),
            data={"days": days},
        )

    if operation == "create":
        title = args.get("title") or args.get("query")
        when = args.get("datetime")
        kind = args.get("kind") or "event"
        if not title or not when:
            return ToolExecutionResult(
                tool=action.tool,
                operation=operation,
                status="needs_clarification",
                message="What should I put on the calendar, and when?",
            )
        item_type = "reminder" if kind == "reminder" else "event"
        alarm = args.get("alarm_minutes_before")
        if item_type == "reminder" and alarm is None:
            alarm = 0
        return ToolExecutionResult(
            tool=action.tool,
            operation=operation,
            status="success",
            message=_create_calendar_item(title, when, item_type, alarm),
            data={"title": title, "datetime": when, "kind": item_type},
        )

    return ToolExecutionResult(
        tool=action.tool,
        operation=operation,
        status="unsupported",
        message="Calendar update/delete is not implemented yet.",
    )


async def execute_wiki_action(action: PlannedAction, latest_text: str) -> ToolExecutionResult:
    _context = load_context_template("tools/wiki.md")
    operation = action.operation or "read"
    args = action.arguments

    if operation == "read":
        query = args.get("query") or latest_text
        return ToolExecutionResult(
            tool=action.tool,
            operation=operation,
            status="success",
            message=await answer_memory_query(query),
            data={"query": query},
        )

    if operation == "create":
        content = args.get("content") or args.get("query") or latest_text
        save_memory_note(content)
        return ToolExecutionResult(
            tool=action.tool,
            operation=operation,
            status="success",
            message=None,
            data={"saved": True},
        )

    if operation == "update":
        path = args.get("path")
        exact_line = args.get("exact_line")
        replacement = args.get("replacement")
        if replacement is None:
            replacement = args.get("content")
        if not path or not exact_line or replacement is None:
            return ToolExecutionResult(
                tool=action.tool,
                operation=operation,
                status="needs_clarification",
                message="Which exact wiki line should I update?",
            )
        return ToolExecutionResult(
            tool=action.tool,
            operation=operation,
            status="success",
            message=update_wiki_line(
                path=path,
                exact_line=exact_line,
                replacement=replacement,
                reason=action.reason,
            ),
            data={"path": path, "exact_line": exact_line},
        )

    if operation == "delete":
        path = args.get("path")
        exact_line = args.get("exact_line")
        if not path or not exact_line:
            return ToolExecutionResult(
                tool=action.tool,
                operation=operation,
                status="needs_clarification",
                message="Which exact wiki line should I delete?",
            )
        return ToolExecutionResult(
            tool=action.tool,
            operation=operation,
            status="success",
            message=delete_wiki_line(path=path, exact_line=exact_line, reason=action.reason),
            data={"path": path, "exact_line": exact_line},
        )

    return ToolExecutionResult(
        tool=action.tool,
        operation=operation,
        status="unsupported",
        message="Wiki operation is not implemented yet.",
    )


def _create_calendar_item(
    title: str,
    when: str,
    item_type: str,
    alarm_minutes_before: int | None,
) -> str:
    from dobby_app.caldav_client import create_calendar_item

    starts_at = parse_datetime(when)
    with session_scope() as session:
        result = create_calendar_item(
            title=title,
            starts_at=starts_at,
            item_type=item_type,
            alarm_minutes_before=alarm_minutes_before,
        )
        session.add(
            CaldavItem(
                uid=result.uid,
                calendar_url=result.url,
                title=title,
                item_type=item_type,
                starts_at=starts_at,
                ends_at=starts_at,
                alarm_minutes_before=alarm_minutes_before,
            )
        )
    return f"Created {item_type}: {title} at {starts_at}."
