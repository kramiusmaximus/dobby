from pathlib import Path

from dobby_app.db.models import ScheduledJob
from dobby_app.workflows.job_seed import seed_default_jobs


def test_seed_default_jobs(tmp_path, monkeypatch, sqlite_session):
    automations = tmp_path / "automations"
    automations.mkdir()
    (automations / "daily.toml").write_text(
        """
version = 1
id = "daily-telegram-message"
name = "DOBBY Daily Telegram Message"
prompt = "send briefing"
status = "ACTIVE"
rrule = "RRULE:FREQ=WEEKLY;BYHOUR=9;BYMINUTE=0;BYDAY=SU,MO,TU,WE,TH,FR,SA"
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("dobby_app.workflows.job_seed.settings.automations_root", Path(automations))
    seed_default_jobs(sqlite_session)
    job = sqlite_session.query(ScheduledJob).one()
    assert job.name == "daily-telegram-message"
    assert job.job_type == "daily_briefing"
    assert job.enabled is True
