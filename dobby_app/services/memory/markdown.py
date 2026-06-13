from __future__ import annotations

import logging
from datetime import date, datetime

from dobby_app.integrations.obsidian import ObsidianHTTPError, get_obsidian_client
from dobby_app.services.memory.constants import LOG_PAGE, MEMORY_INBOX, MONTH_NAMES

logger = logging.getLogger(__name__)


def calendar_page_path(starts_at: datetime) -> str:
    month = MONTH_NAMES[starts_at.month]
    return f"pages/calendar/{month}-{starts_at.year}-commitments.md"


def ensure_memory_inbox(today: str) -> None:
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


def ensure_calendar_page(rel_path: str, starts_at: datetime, today: str) -> None:
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


def obsidian_patch_frontmatter(path: str, key: str, value: str) -> None:
    get_obsidian_client().patch(
        path,
        f'"{value}"',
        operation="replace",
        target_type="frontmatter",
        target=key,
        content_type="application/json",
    )


def try_patch_frontmatter(path: str, key: str, value: str) -> None:
    try:
        obsidian_patch_frontmatter(path, key, value)
    except ObsidianHTTPError as exc:
        logger.warning("Could not patch Obsidian frontmatter for %s: %s", path, exc)
        return


def replace_exact_line(content: str, exact_line: str, replacement: str) -> str:
    lines = content.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == exact_line]
    if not matches:
        raise ValueError("Exact line was not found in the memory page.")
    if len(matches) > 1:
        raise ValueError("Exact line appears more than once; refusing ambiguous memory update.")
    newline = line_ending(lines[matches[0]])
    lines[matches[0]] = replacement + newline
    return "".join(lines)


def delete_exact_line(content: str, exact_line: str) -> str:
    lines = content.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == exact_line]
    if not matches:
        raise ValueError("Exact line was not found in the memory page.")
    if len(matches) > 1:
        raise ValueError("Exact line appears more than once; refusing ambiguous memory delete.")
    del lines[matches[0]]
    return "".join(lines)


def line_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    return ""


def append_memory_log(entry: str) -> None:
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


def try_append_memory_log(entry: str) -> None:
    try:
        append_memory_log(entry)
    except ObsidianHTTPError as exc:
        logger.warning("Could not append Obsidian memory log entry: %s", exc)


def coerce_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
