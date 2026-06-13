from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from dobby_app.assistant.llm_logging import reasoning


async def create_response(
    *,
    api_key: str,
    model: str,
    reasoning_effort: str,
    **kwargs: Any,
) -> Any:
    client = AsyncOpenAI(api_key=api_key)
    return await client.responses.create(
        model=model,
        reasoning=reasoning(reasoning_effort),
        **kwargs,
    )
