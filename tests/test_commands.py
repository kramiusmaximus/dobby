from __future__ import annotations

from datetime import datetime

from dobby_app.commands import handle_command
from dobby_app.integrations.caldav_client import CalendarWriteResult
from dobby_app.core.models import CaldavItem, JobRun, ScheduledJob


def _add_job(sqlite_session, *, enabled: bool = True) -> ScheduledJob:
    job = ScheduledJob(
        name="daily-briefing",
        display_name="Daily Briefing",
        enabled=enabled,
        schedule_text="every day at 9:00",
        cron={"hour": 9, "minute": 0},
        prompt="Brief Mark",
        job_type="daily_briefing",
    )
    sqlite_session.add(job)
    sqlite_session.flush()
    return job


def test_jobs_lists_configured_jobs(sqlite_session):
    _add_job(sqlite_session)

    response = handle_command(sqlite_session, "/jobs")

    assert "daily-briefing" in response
    assert "active" in response
    assert "every day at 9:00" in response


def test_removed_help_command_is_unknown(sqlite_session):
    assert handle_command(sqlite_session, "/help") == "Unknown command."


def test_removed_commands_alias_is_unknown(sqlite_session):
    assert handle_command(sqlite_session, "/commands") == "Unknown command."


def test_removed_whoami_command_is_unknown(sqlite_session):
    assert handle_command(sqlite_session, "/whoami") == "Unknown command."


def test_status_reports_polling(sqlite_session):
    response = handle_command(sqlite_session, "/status")

    assert "DOBBY is running" in response
    assert "polling every" in response


def test_memory_queries_wiki(sqlite_session):
    response = handle_command(sqlite_session, "/memory TouchDesigner")

    assert response == "Memory queries are handled by DOBBY's Obsidian-backed agent."


def test_memory_save_updates_obsidian_wiki(monkeypatch, sqlite_session):
    class FakeObsidianClient:
        def __init__(self):
            self.calls = []

        def read(self, path):
            self.calls.append(("read", path))
            return "existing"

        def patch(self, *args, **kwargs):
            self.calls.append(("patch", args, kwargs))
            return ""

        def append(self, *args, **kwargs):
            self.calls.append(("append", args, kwargs))
            return ""

    client = FakeObsidianClient()
    monkeypatch.setattr("dobby_app.memory.wiki_memory.obsidian_is_enabled", lambda: True)
    monkeypatch.setattr("dobby_app.memory.wiki_memory.get_obsidian_client", lambda: client)

    response = handle_command(sqlite_session, "/memory save Mark prefers concise Telegram acknowledgements")

    assert response == "Saved to memory."
    assert any(call[0] == "patch" for call in client.calls)
    assert any(
        call[0] == "append" and "Mark prefers concise Telegram acknowledgements" in call[1][1]
        for call in client.calls
    )


def test_queue_lists_recent_job_runs(sqlite_session):
    job = _add_job(sqlite_session)
    sqlite_session.add(JobRun(scheduled_job_id=job.id, status="failed", error="boom"))
    sqlite_session.flush()

    response = handle_command(sqlite_session, "/queue")

    assert "Recent queue runs:" in response
    assert "failed" in response
    assert "boom" in response


def test_today_lists_one_day_of_calendar_items(monkeypatch, sqlite_session):
    captured = {}
    synced = []

    def fake_list_items(start, end, calendar_name=None):
        captured["days"] = (end - start).days
        return [{"summary": "Dentist", "start": datetime(2026, 6, 8, 9, 0)}]

    monkeypatch.setattr("dobby_app.scheduling.calendar_service.list_items", fake_list_items)
    monkeypatch.setattr("dobby_app.scheduling.calendar_service.sync_calendar_snapshot_to_wiki", lambda items: synced.extend(items))

    response = handle_command(sqlite_session, "/today")

    assert captured["days"] == 1
    assert synced == [{"summary": "Dentist", "start": datetime(2026, 6, 8, 9, 0)}]
    assert "Dentist" in response


def test_upcoming_lists_fourteen_days_of_calendar_items(monkeypatch, sqlite_session):
    captured = {}
    synced = []

    def fake_list_items(start, end, calendar_name=None):
        captured["days"] = (end - start).days
        return [{"summary": "Studio", "start": datetime(2026, 6, 12, 15, 0)}]

    monkeypatch.setattr("dobby_app.scheduling.calendar_service.list_items", fake_list_items)
    monkeypatch.setattr("dobby_app.scheduling.calendar_service.sync_calendar_snapshot_to_wiki", lambda items: synced.extend(items))

    response = handle_command(sqlite_session, "/upcoming")

    assert captured["days"] == 14
    assert synced == [{"summary": "Studio", "start": datetime(2026, 6, 12, 15, 0)}]
    assert "Studio" in response


def test_remind_creates_calendar_reminder(monkeypatch, sqlite_session):
    created = {}
    calls = []
    starts_at = datetime(2026, 6, 8, 9, 0)

    monkeypatch.setattr("dobby_app.commands.calendar.parse_datetime", lambda text: starts_at)
    monkeypatch.setattr(
        "dobby_app.scheduling.calendar_service.sync_calendar_item_to_wiki",
        lambda **kwargs: calls.append(("wiki", kwargs)) or "pages/calendar/june-2026-commitments.md",
    )

    def fake_create_calendar_item(**kwargs):
        calls.append(("caldav", kwargs))
        created.update(kwargs)
        return CalendarWriteResult(uid="reminder-uid", url="caldav://reminder")

    monkeypatch.setattr("dobby_app.scheduling.calendar_service.create_calendar_item", fake_create_calendar_item)

    response = handle_command(sqlite_session, "/remind Call dentist at tomorrow 9")

    assert created["title"] == "Call dentist"
    assert created["item_type"] == "reminder"
    assert created["alarm_minutes_before"] == 0
    assert [name for name, _ in calls] == ["wiki", "caldav"]
    item = sqlite_session.query(CaldavItem).filter_by(uid="reminder-uid").one()
    assert item.wiki_page == "pages/calendar/june-2026-commitments.md"
    assert "Created reminder: Call dentist" in response


def test_event_creates_calendar_event(monkeypatch, sqlite_session):
    created = {}
    calls = []
    starts_at = datetime(2026, 6, 12, 15, 0)

    monkeypatch.setattr("dobby_app.commands.calendar.parse_datetime", lambda text: starts_at)
    monkeypatch.setattr(
        "dobby_app.scheduling.calendar_service.sync_calendar_item_to_wiki",
        lambda **kwargs: calls.append(("wiki", kwargs)) or "pages/calendar/june-2026-commitments.md",
    )

    def fake_create_calendar_item(**kwargs):
        calls.append(("caldav", kwargs))
        created.update(kwargs)
        return CalendarWriteResult(uid="event-uid", url="caldav://event")

    monkeypatch.setattr("dobby_app.scheduling.calendar_service.create_calendar_item", fake_create_calendar_item)

    response = handle_command(sqlite_session, "/event Studio visit at Friday 15:00")

    assert created["title"] == "Studio visit"
    assert created["item_type"] == "event"
    assert created["alarm_minutes_before"] is None
    assert [name for name, _ in calls] == ["wiki", "caldav"]
    item = sqlite_session.query(CaldavItem).filter_by(uid="event-uid").one()
    assert item.wiki_page == "pages/calendar/june-2026-commitments.md"
    assert "Created event: Studio visit" in response


def test_job_show_displays_job_config(sqlite_session):
    _add_job(sqlite_session)

    response = handle_command(sqlite_session, "/job show daily-briefing")

    assert "Daily Briefing" in response
    assert "name: daily-briefing" in response
    assert "type: daily_briefing" in response


def test_job_run_enqueues_job(monkeypatch, sqlite_session):
    job = _add_job(sqlite_session)

    def fake_enqueue_job(session, queued_job):
        assert queued_job.id == job.id
        run = JobRun(scheduled_job_id=queued_job.id, status="queued")
        session.add(run)
        session.flush()
        return run

    monkeypatch.setattr("dobby_app.commands.jobs.enqueue_job", fake_enqueue_job)

    response = handle_command(sqlite_session, "/job run daily-briefing")

    assert "Queued Daily Briefing as run #" in response


def test_job_pause_disables_job(sqlite_session):
    job = _add_job(sqlite_session)

    response = handle_command(sqlite_session, "/job pause daily-briefing")

    assert response == "Paused Daily Briefing."
    assert job.enabled is False


def test_job_resume_enables_job(sqlite_session):
    job = _add_job(sqlite_session, enabled=False)

    response = handle_command(sqlite_session, "/job resume daily-briefing")

    assert response == "Resumed Daily Briefing."
    assert job.enabled is True


def test_job_schedule_updates_schedule(sqlite_session):
    job = _add_job(sqlite_session)

    response = handle_command(sqlite_session, "/job schedule daily-briefing every 2 hours")

    assert response == "Updated Daily Briefing schedule to: every 2 hours."
    assert job.schedule_text == "every 2 hours"
    assert job.cron == {"hour": "*/2", "minute": 0}


def test_job_retry_enqueues_original_job(monkeypatch, sqlite_session):
    job = _add_job(sqlite_session)
    failed_run = JobRun(scheduled_job_id=job.id, status="failed", error="boom")
    sqlite_session.add(failed_run)
    sqlite_session.flush()

    def fake_enqueue_job(session, queued_job):
        run = JobRun(scheduled_job_id=queued_job.id, status="queued")
        session.add(run)
        session.flush()
        return run

    monkeypatch.setattr("dobby_app.commands.jobs.enqueue_job", fake_enqueue_job)

    response = handle_command(sqlite_session, f"/job retry {failed_run.id}")

    assert "Retried Daily Briefing as run #" in response


def test_unknown_command_returns_helpful_message(sqlite_session):
    assert handle_command(sqlite_session, "/nope") == "Unknown command."
