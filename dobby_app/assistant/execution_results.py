from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ToolStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class ToolExecutionResult:
    tool: str
    operation: str | None
    status: ToolStatus | str
    message: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "status", ToolStatus(self.status))
        except ValueError:
            pass

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
