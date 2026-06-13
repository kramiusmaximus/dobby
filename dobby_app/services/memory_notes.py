from __future__ import annotations

import logging
from datetime import date, datetime

from dobby_app.integrations.obsidian import ObsidianHTTPError, get_obsidian_client, obsidian_is_enabled


logger = logging.getLogger(__name__)
MEMORY_INBOX = "pages/concepts/telegram-memory-inbox.md"
LOG_PAGE = "log.md"
MONTH_NAMES = {
    1: "january",
    2: "february",
    3: "march",
    4: "april",
    5: "may",
    6: "june",
    7: "july",
    8: "august",
    9: "september",
    10: "october",
    11: "november",
    12: "december",
}


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
    _ensure_memory_inbox(today)
    _obsidian_patch_frontmatter(MEMORY_INBOX, "updated", today)
    get_obsidian_client().append(MEMORY_INBOX, f"\n\n## {today}\n\n- {note}\n")
    _append_memory_log(f"\n## [{today}] memory | Telegram Memory Inbox\n\n- Saved memory note: {note}\n")


def update_memory_line(*, path: str, exact_line: str, replacement: str, reason: str | None = None) -> str:
    if not obsidian_is_enabled():
        raise RuntimeError("Obsidian API is not configured; memory writes are unavailable.")
    if not path.strip() or not exact_line.strip():
        raise ValueError("Memory update requires a path and exact_line.")

    today = date.today().isoformat()
    client = get_obsidian_client()
    content = client.read(path)
    updated = _replace_exact_line(content, exact_line, replacement)
    client.write(path, updated)
    _try_patch_frontmatter(path, "updated", today)
    _try_append_memory_log(
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
    updated = _delete_exact_line(content, exact_line)
    client.write(path, updated)
    _try_patch_frontmatter(path, "updated", today)
    _try_append_memory_log(
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
        starts_at = _coerce_datetime(item.get("start"))
        if not title or not starts_at:
            continue
        _sync_calendar_marker_to_memory(
            title=title,
            starts_at=starts_at,
            item_type="calendar",
            status="calendar read sync",
            log=False,
        )


def _calendar_page_path(starts_at: datetime) -> str:
    month = MONTH_NAMES[starts_at.month]
    return f"pages/calendar/{month}-{starts_at.year}-commitments.md"


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
    rel_path = _calendar_page_path(starts_at)
    _ensure_calendar_page(rel_path, starts_at, today)
    _obsidian_patch_frontmatter(rel_path, "updated", today)

    timestamp = starts_at.isoformat()
    marker = f"- {timestamp}: {title} ({item_type}; {status})"
    content = get_obsidian_client().read(rel_path)
    if marker not in content:
        if "\n## Calendar Sync\n" in content:
            get_obsidian_client().append(rel_path, f"{marker}\n", target_type="heading", target="Calendar Sync")
        else:
            get_obsidian_client().append(rel_path, f"\n\n## Calendar Sync\n\n{marker}\n")

    if log:
        entry = (
            f"\n## [{today}] calendar-sync | {title}\n\n"
            f"- Synced Obsidian calendar source before CalDAV write.\n"
            f"- Memory page: {rel_path}\n"
            f"- Scheduled time: {timestamp}\n"
            f"- Type: {item_type}\n"
        )
        _try_append_memory_log(entry)

    return rel_path


def _ensure_memory_inbox(today: str) -> None:
    client = get_obsidian_client()
    try:
        client.read(MEMORY_INBOX)
        return
    except ObsidianHTTPError as exc:
        if exc.status_code != 404:
            raise

    client.write(
        MEMORY_INBOX,
        "\n".join(
            [
                "---",
                "title: Telegram Memory Inbox",
                "type: concept",
                f"created: {today}",
                f"updated: {today}",
                "status: active",
                "tags: [telegram, memory]",
                "sources: []",
                "---",
                "",
                "# Telegram Memory Inbox",
                "",
                "Durable memory captured from Telegram before it is filed into a more specific memory page.",
                "",
            ]
        ),
    )


def _ensure_calendar_page(rel_path: str, starts_at: datetime, today: str) -> None:
    client = get_obsidian_client()
    try:
        client.read(rel_path)
        return
    except ObsidianHTTPError as exc:
        if exc.status_code != 404:
            raise

    display_month = starts_at.strftime("%B %Y")
    client.write(
        rel_path,
        "\n".join(
            [
                "---",
                f"title: {display_month} Commitments",
                "type: calendar",
                f"created: {today}",
                f"updated: {today}",
                "status: active",
                f"tags: [calendar, {starts_at.year}-{starts_at.month:02d}, commitments]",
                "sources: []",
                "---",
                "",
                f"# {display_month} Commitments",
                "",
            ]
        ),
    )


def _obsidian_patch_frontmatter(path: str, key: str, value: str) -> None:
    get_obsidian_client().patch(
        path,
        f'"{value}"',
        operation="replace",
        target_type="frontmatter",
        target=key,
        content_type="application/json",
    )


def _try_patch_frontmatter(path: str, key: str, value: str) -> None:
    try:
        _obsidian_patch_frontmatter(path, key, value)
    except ObsidianHTTPError as exc:
        # Some ad hoc notes may not have frontmatter yet. The line mutation already succeeded.
        logger.warning("Could not patch Obsidian frontmatter for %s: %s", path, exc)
        return


def _replace_exact_line(content: str, exact_line: str, replacement: str) -> str:
    lines = content.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == exact_line]
    if not matches:
        raise ValueError("Exact line was not found in the memory page.")
    if len(matches) > 1:
        raise ValueError("Exact line appears more than once; refusing ambiguous memory update.")
    newline = _line_ending(lines[matches[0]])
    lines[matches[0]] = replacement + newline
    return "".join(lines)


def _delete_exact_line(content: str, exact_line: str) -> str:
    lines = content.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == exact_line]
    if not matches:
        raise ValueError("Exact line was not found in the memory page.")
    if len(matches) > 1:
        raise ValueError("Exact line appears more than once; refusing ambiguous memory delete.")
    del lines[matches[0]]
    return "".join(lines)


def _line_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    return ""


def _append_memory_log(entry: str) -> None:
    client = get_obsidian_client()
    try:
        client.read(LOG_PAGE)
    except ObsidianHTTPError as exc:
        if exc.status_code != 404:
            raise
        today = date.today().isoformat()
        client.write(
            LOG_PAGE,
            "\n".join(
                [
                    "---",
                    "title: DOBBY Log",
                    "type: log",
                    f"created: {today}",
                    f"updated: {today}",
                    "status: active",
                    "tags: []",
                    "sources: []",
                    "---",
                    "",
                    "# DOBBY Log",
                    "",
                ]
            ),
        )
    client.append(LOG_PAGE, entry.rstrip() + "\n")


def _try_append_memory_log(entry: str) -> None:
    try:
        _append_memory_log(entry)
    except ObsidianHTTPError as exc:
        # Audit logging should not turn an already-applied memory mutation into a user-visible failure.
        logger.warning("Could not append Obsidian memory log entry: %s", exc)


def _coerce_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
