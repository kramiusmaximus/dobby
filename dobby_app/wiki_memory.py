from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re

from dobby_app.config import settings


MEMORY_INBOX = "pages/concepts/telegram-memory-inbox.md"
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


@dataclass(frozen=True)
class MemoryHit:
    path: Path
    title: str
    snippet: str
    score: int


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

    return query_memory(rest)


def query_memory(query: str, *, limit: int = 5) -> str:
    terms = _terms(query)
    if not terms:
        return "What should I search memory for?"

    hits = sorted(_search_files(terms), key=lambda hit: hit.score, reverse=True)[:limit]
    if not hits:
        return f"No saved memory matched: {query}"

    lines = [f"Memory matches for: {query}"]
    for hit in hits:
        rel = hit.path.relative_to(settings.wiki_root)
        lines.append(f"- {hit.title} ({rel}): {hit.snippet}")
    return "\n".join(lines)


def save_memory_note(note: str) -> None:
    today = date.today().isoformat()
    page = settings.wiki_root / MEMORY_INBOX
    page.parent.mkdir(parents=True, exist_ok=True)

    if not page.exists():
        page.write_text(
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
                    "Durable memory captured from Telegram before it is filed into a more specific wiki page.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    content = page.read_text(encoding="utf-8")
    content = _set_frontmatter_value(content, "updated", today)
    content = content.rstrip() + f"\n\n## {today}\n\n- {note}\n"
    page.write_text(content, encoding="utf-8")

    log = settings.wiki_root / "log.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    existing = log.read_text(encoding="utf-8") if log.exists() else ""
    entry = f"\n## [{today}] memory | Telegram Memory Inbox\n\n- Saved memory note: {note}\n"
    log.write_text(existing.rstrip() + entry + "\n", encoding="utf-8")


def sync_calendar_item_to_wiki(*, title: str, starts_at: datetime, item_type: str) -> str:
    return _sync_calendar_marker_to_wiki(
        title=title,
        starts_at=starts_at,
        item_type=item_type,
        status="calendar sync pending",
        log=True,
    )


def sync_calendar_snapshot_to_wiki(items: list[dict]) -> None:
    for item in items:
        title = str(item.get("summary") or "").strip()
        starts_at = _coerce_datetime(item.get("start"))
        if not title or not starts_at:
            continue
        _sync_calendar_marker_to_wiki(
            title=title,
            starts_at=starts_at,
            item_type="calendar",
            status="calendar read sync",
            log=False,
        )


def _search_files(terms: list[str]) -> list[MemoryHit]:
    root = settings.wiki_root
    if not root.exists():
        return []

    hits = []
    for path in root.rglob("*.md"):
        if any(part in {"raw", "tmp"} for part in path.relative_to(root).parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lowered = text.lower()
        score = sum(lowered.count(term) for term in terms)
        if score <= 0:
            continue
        hits.append(MemoryHit(path=path, title=_title_for(path, text), snippet=_snippet(text, terms), score=score))
    return hits


def _title_for(path: Path, text: str) -> str:
    match = re.search(r"^title:\s*(.+)$", text, flags=re.MULTILINE)
    if match:
        return match.group(1).strip()
    heading = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    if heading:
        return heading.group(1).strip()
    return path.stem.replace("-", " ").title()


def _snippet(text: str, terms: list[str]) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    lowered = normalized.lower()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    start = max(min(positions) - 80, 0) if positions else 0
    snippet = normalized[start : start + 220].strip()
    return ("..." if start else "") + snippet


def _terms(query: str) -> list[str]:
    return [term.lower() for term in re.findall(r"[\wА-Яа-яЁё]+", query) if len(term) > 1]


def _set_frontmatter_value(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}:\s*.*$", flags=re.MULTILINE)
    replacement = f"{key}: {value}"
    if pattern.search(content):
        return pattern.sub(replacement, content, count=1)
    return content


def _calendar_page_path(starts_at: datetime) -> str:
    month = MONTH_NAMES[starts_at.month]
    return f"pages/calendar/{month}-{starts_at.year}-commitments.md"


def _sync_calendar_marker_to_wiki(
    *,
    title: str,
    starts_at: datetime,
    item_type: str,
    status: str,
    log: bool,
) -> str:
    today = date.today().isoformat()
    rel_path = _calendar_page_path(starts_at)
    page = settings.wiki_root / rel_path
    page.parent.mkdir(parents=True, exist_ok=True)

    if not page.exists():
        display_month = starts_at.strftime("%B %Y")
        page.write_text(
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
            encoding="utf-8",
        )

    content = page.read_text(encoding="utf-8")
    content = _set_frontmatter_value(content, "updated", today)
    timestamp = starts_at.isoformat()
    marker = f"- {timestamp}: {title} ({item_type}; {status})"
    if marker not in content:
        if "\n## Calendar Sync\n" in content:
            content = content.rstrip() + f"\n{marker}\n"
        else:
            content = content.rstrip() + f"\n\n## Calendar Sync\n\n{marker}\n"
    page.write_text(content, encoding="utf-8")

    if log:
        wiki_log = settings.wiki_root / "log.md"
        wiki_log.parent.mkdir(parents=True, exist_ok=True)
        existing = wiki_log.read_text(encoding="utf-8") if wiki_log.exists() else ""
        entry = (
            f"\n## [{today}] calendar-sync | {title}\n\n"
            f"- Synced Obsidian calendar source before CalDAV write.\n"
            f"- Wiki page: {rel_path}\n"
            f"- Scheduled time: {timestamp}\n"
            f"- Type: {item_type}\n"
        )
        wiki_log.write_text(existing.rstrip() + entry + "\n", encoding="utf-8")

    return rel_path


def _coerce_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None
