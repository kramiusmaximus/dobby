from __future__ import annotations

from datetime import datetime

from dobby_app.commands import handle_command
from dobby_app.caldav_client import CalendarWriteResult
from dobby_app.models import JobRun, ScheduledJob


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

    def fake_list_items(start, end):
        captured["days"] = (end - start).days
        return [{"summary": "Dentist", "start": datetime(2026, 6, 8, 9, 0)}]

    monkeypatch.setattr("dobby_app.commands.list_items", fake_list_items)

    response = handle_command(sqlite_session, "/today")

    assert captured["days"] == 1
    assert "Dentist" in response


def test_upcoming_lists_fourteen_days_of_calendar_items(monkeypatch, sqlite_session):
    captured = {}

    def fake_list_items(start, end):
        captured["days"] = (end - start).days
        return [{"summary": "Studio", "start": datetime(2026, 6, 12, 15, 0)}]

    monkeypatch.setattr("dobby_app.commands.list_items", fake_list_items)

    response = handle_command(sqlite_session, "/upcoming")

    assert captured["days"] == 14
    assert "Studio" in response


def test_remind_creates_calendar_reminder(monkeypatch, sqlite_session):
    created = {}
    starts_at = datetime(2026, 6, 8, 9, 0)

    monkeypatch.setattr("dobby_app.commands.parse_datetime", lambda text: starts_at)

    def fake_create_calendar_item(**kwargs):
        created.update(kwargs)
        return CalendarWriteResult(uid="reminder-uid", url="caldav://reminder")

    monkeypatch.setattr("dobby_app.commands.create_calendar_item", fake_create_calendar_item)

    response = handle_command(sqlite_session, "/remind Call dentist at tomorrow 9")

    assert created["title"] == "Call dentist"
    assert created["item_type"] == "reminder"
    assert created["alarm_minutes_before"] == 0
    assert "Created reminder: Call dentist" in response


def test_event_creates_calendar_event(monkeypatch, sqlite_session):
    created = {}
    starts_at = datetime(2026, 6, 12, 15, 0)

    monkeypatch.setattr("dobby_app.commands.parse_datetime", lambda text: starts_at)

    def fake_create_calendar_item(**kwargs):
        created.update(kwargs)
        return CalendarWriteResult(uid="event-uid", url="caldav://event")

    monkeypatch.setattr("dobby_app.commands.create_calendar_item", fake_create_calendar_item)

    response = handle_command(sqlite_session, "/event Studio visit at Friday 15:00")

    assert created["title"] == "Studio visit"
    assert created["item_type"] == "event"
    assert created["alarm_minutes_before"] is None
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

    monkeypatch.setattr("dobby_app.commands.enqueue_job", fake_enqueue_job)

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

    monkeypatch.setattr("dobby_app.commands.enqueue_job", fake_enqueue_job)

    response = handle_command(sqlite_session, f"/job retry {failed_run.id}")

    assert "Retried Daily Briefing as run #" in response


def test_unknown_command_returns_helpful_message(sqlite_session):
    assert handle_command(sqlite_session, "/nope") == "Unknown command."
