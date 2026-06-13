from __future__ import annotations

from datetime import date, datetime

from dobby_app.integrations.obsidian import get_obsidian_client, obsidian_is_enabled
from dobby_app.services.memory.markdown import (
    calendar_page_path,
    coerce_datetime,
    ensure_calendar_page,
    obsidian_patch_frontmatter,
    try_append_memory_log,
)


def sync_calendar_item_to_memory(*, title: str, starts_at: datetime, item_type: str) -> str:
    return _sync_calendar_marker_to_memory(
        title=title,
        starts_at=starts_at,
        item_type=item_type,
        status="calendar sync pending",
        log=True,
    )


def sync_calendar_snapshot_to_memory(items: list[dict]) -> None:
    for item in items:
        title = str(item.get("summary") or "").strip()
        starts_at = coerce_datetime(item.get("start"))
        if not title or not starts_at:
            continue
        _sync_calendar_marker_to_memory(
            title=title,
            starts_at=starts_at,
            item_type="calendar",
            status="calendar read sync",
            log=False,
        )


def _sync_calendar_marker_to_memory(
    *,
    title: str,
    starts_at: datetime,
    item_type: str,
    status: str,
    log: bool,
) -> str:
    if not obsidian_is_enabled():
        raise RuntimeError("Obsidian API is not configured; memory calendar sync is unavailable.")

    today = date.today().isoformat()
    rel_path = calendar_page_path(starts_at)
    ensure_calendar_page(rel_path, starts_at, today)
    obsidian_patch_frontmatter(rel_path, "updated", today)

    timestamp = starts_at.isoformat()
    marker = f"- {timestamp}: {title} ({item_type}; {status})"
    client = get_obsidian_client()
    content = client.read(rel_path)
    if marker not in content:
        if "\n## Calendar Sync\n" in content:
            client.append(rel_path, f"{marker}\n", target_type="heading", target="Calendar Sync")
        else:
            client.append(rel_path, f"\n\n## Calendar Sync\n\n{marker}\n")

    if log:
        entry = (
            f"\n## [{today}] calendar-sync | {title}\n\n"
            f"- Synced Obsidian calendar source before CalDAV write.\n"
            f"- Memory page: {rel_path}\n"
            f"- Scheduled time: {timestamp}\n"
            f"- Type: {item_type}\n"
        )
        try_append_memory_log(entry)

    return rel_path
