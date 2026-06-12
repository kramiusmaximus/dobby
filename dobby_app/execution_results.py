from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
