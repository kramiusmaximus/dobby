from __future__ import annotations

from datetime import date

from dobby_app.integrations.obsidian import get_obsidian_client, obsidian_is_enabled
from dobby_app.services.memory.constants import MEMORY_INBOX
from dobby_app.services.memory.markdown import append_memory_log, ensure_memory_inbox, obsidian_patch_frontmatter


def handle_memory_command(text: str) -> str:
    rest = text.strip()
    if not rest:
        return "Use `/memory <query>` to search memory, or `/memory save <note>` to save durable context."

    action, _, remainder = rest.partition(" ")
    if action.lower() in {"save", "remember"}:
        note = remainder.strip()
        if not note:
            return "What should I save to memory?"
        save_memory_note(note)
        return "Saved to memory."

    return "Memory queries are handled by DOBBY's Obsidian-backed agent."


def save_memory_note(note: str) -> None:
    if not obsidian_is_enabled():
        raise RuntimeError("Obsidian API is not configured; memory writes are unavailable.")

    today = date.today().isoformat()
    ensure_memory_inbox(today)
    obsidian_patch_frontmatter(MEMORY_INBOX, "updated", today)
    get_obsidian_client().append(MEMORY_INBOX, f"\n\n## {today}\n\n- {note}\n")
    append_memory_log(f"\n## [{today}] memory | Telegram Memory Inbox\n\n- Saved memory note: {note}\n")
