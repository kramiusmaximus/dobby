from __future__ import annotations

from datetime import datetime
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from sqlalchemy.orm import Session

from dobby_app.core.config import settings
from dobby_app.core.models import ScheduledJob
from dobby_app.scheduling.schedules import rrule_to_cron


JOB_TYPES = {
    "daily-telegram-message": "daily_briefing",
    "dobby-wiki-maintenance": "wiki_maintenance",
}


def seed_default_jobs(session: Session) -> None:
    root = Path(settings.automations_root)
    if not root.exists():
        return

    for path in sorted(root.glob("*.toml")):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        name = data.get("id") or path.stem
        existing = session.query(ScheduledJob).filter_by(name=name).one_or_none()
        if existing:
            continue
        parsed = rrule_to_cron(data["rrule"])
        session.add(
            ScheduledJob(
                name=name,
                display_name=data.get("name", name),
                enabled=data.get("status", "ACTIVE") == "ACTIVE",
                schedule_text=parsed.schedule_text,
                cron=parsed.cron,
                prompt=data.get("prompt", ""),
                job_type=JOB_TYPES.get(name, "generic"),
                updated_at=datetime.utcnow(),
            )
        )
