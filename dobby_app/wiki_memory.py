from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re

from dobby_app.config import settings


MEMORY_INBOX = "pages/concepts/telegram-memory-inbox.md"


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
