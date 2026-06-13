from __future__ import annotations

import os
import subprocess
from pathlib import Path

from dobby_app.config.settings import settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = PROJECT_ROOT / ".dobby-version"


def current_commit() -> str:
    env_commit = os.environ.get("DOBBY_COMMIT") or os.environ.get("GITHUB_SHA")
    if env_commit:
        return _short_commit(env_commit)
    if VERSION_FILE.exists():
        return _short_commit(VERSION_FILE.read_text(encoding="utf-8").strip())
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if completed.returncode == 0 and completed.stdout.strip():
        return completed.stdout.strip()
    return "unknown"


def runtime_status(service: str) -> dict[str, str | int | bool]:
    return {
        "ok": True,
        "service": service,
        "commit": current_commit(),
        "telegram_poll_interval_seconds": settings.telegram_poll_interval_seconds,
        "obsidian_enabled": settings.effective_obsidian_enabled,
    }


def format_startup_message(service: str, status: dict[str, str | int | bool]) -> str:
    return "\n".join(
        [
            "DOBBY deployed",
            "",
            f"Service: {service}",
            f"Commit: {status.get('commit', 'unknown')}",
            "Status: ok",
            f"Polling: every {status.get('telegram_poll_interval_seconds')} seconds",
            f"Obsidian: {'enabled' if status.get('obsidian_enabled') else 'disabled'}",
        ]
    )


def _short_commit(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return "unknown"
    return cleaned[:12]
