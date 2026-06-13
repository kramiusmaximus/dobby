from __future__ import annotations

from datetime import date

from dobby_app.integrations.obsidian import get_obsidian_client, obsidian_is_enabled
from dobby_app.services.memory.markdown import (
    delete_exact_line,
    replace_exact_line,
    try_append_memory_log,
    try_patch_frontmatter,
)


def update_memory_line(*, path: str, exact_line: str, replacement: str, reason: str | None = None) -> str:
    if not obsidian_is_enabled():
        raise RuntimeError("Obsidian API is not configured; memory writes are unavailable.")
    if not path.strip() or not exact_line.strip():
        raise ValueError("Memory update requires a path and exact_line.")

    today = date.today().isoformat()
    client = get_obsidian_client()
    content = client.read(path)
    updated = replace_exact_line(content, exact_line, replacement)
    client.write(path, updated)
    try_patch_frontmatter(path, "updated", today)
    try_append_memory_log(
        "\n".join(
            [
                f"\n## [{today}] memory-update | {path}",
                "",
                f"- Replaced exact line: {exact_line}",
                f"- Replacement: {replacement}",
                f"- Reason: {reason or 'not specified'}",
                "",
            ]
        )
    )
    return f"Updated memory line in {path}."


def delete_memory_line(*, path: str, exact_line: str, reason: str | None = None) -> str:
    if not obsidian_is_enabled():
        raise RuntimeError("Obsidian API is not configured; memory writes are unavailable.")
    if not path.strip() or not exact_line.strip():
        raise ValueError("Memory delete requires a path and exact_line.")

    today = date.today().isoformat()
    client = get_obsidian_client()
    content = client.read(path)
    updated = delete_exact_line(content, exact_line)
    client.write(path, updated)
    try_patch_frontmatter(path, "updated", today)
    try_append_memory_log(
        "\n".join(
            [
                f"\n## [{today}] memory-delete | {path}",
                "",
                f"- Deleted exact line: {exact_line}",
                f"- Reason: {reason or 'not specified'}",
                "",
            ]
        )
    )
    return f"Deleted memory line from {path}."
