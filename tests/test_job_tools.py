from __future__ import annotations

from contextlib import contextmanager

from dobby_app.assistant.execution_results import ToolStatus
from dobby_app.assistant.tools.jobs import functions as job_functions
from dobby_app.db.models import JobRun, ScheduledJob


@contextmanager
def _session_scope(sqlite_session):
    yield sqlite_session
    sqlite_session.commit()


def test_jobs_create_tool_uses_shared_service(monkeypatch, sqlite_session):
    monkeypatch.setattr(job_functions, "session_scope", lambda: _session_scope(sqlite_session))

    result = job_functions.jobs_create(
        name="weekly-review",
        schedule="Sundays at 11",
        prompt="Review Mark's week and send a summary",
        display_name="Weekly Review",
        enabled=True,
    )

    job = sqlite_session.query(ScheduledJob).filter_by(name="weekly-review").one()
    assert result.status == ToolStatus.SUCCESS
    assert result.message == "Created Weekly Review."
    assert job.job_type == "planner_prompt"
    assert job.prompt == "Review Mark's week and send a summary"


def test_jobs_delete_tool_requires_exact_match(monkeypatch, sqlite_session):
    monkeypatch.setattr(job_functions, "session_scope", lambda: _session_scope(sqlite_session))
    sqlite_session.add_all(
        [
            ScheduledJob(
                name="daily-briefing",
                display_name="Daily Briefing",
                enabled=True,
                schedule_text="every day at 9:00",
                cron={"hour": 9, "minute": 0},
                prompt="Brief Mark",
                job_type="planner_prompt",
            ),
            ScheduledJob(
                name="daily-review",
                display_name="Daily Review",
                enabled=True,
                schedule_text="every day at 21:00",
                cron={"hour": 21, "minute": 0},
                prompt="Review Mark's day",
                job_type="planner_prompt",
            ),
        ]
    )
    sqlite_session.flush()

    result = job_functions.jobs_delete("daily")

    assert result.status == ToolStatus.NEEDS_CLARIFICATION
    assert "Which exact job should I delete?" in result.message
    assert sqlite_session.query(ScheduledJob).count() == 2


def test_jobs_run_tool_enqueues_selected_job(monkeypatch, sqlite_session):
    monkeypatch.setattr(job_functions, "session_scope", lambda: _session_scope(sqlite_session))
    job = ScheduledJob(
        name="daily-briefing",
        display_name="Daily Briefing",
        enabled=True,
        schedule_text="every day at 9:00",
        cron={"hour": 9, "minute": 0},
        prompt="Brief Mark",
        job_type="planner_prompt",
    )
    sqlite_session.add(job)
    sqlite_session.flush()

    def fake_enqueue_named_job(session, name):
        run = JobRun(scheduled_job_id=job.id, status="queued")
        session.add(run)
        session.flush()
        return run

    monkeypatch.setattr(job_functions, "enqueue_named_job", fake_enqueue_named_job)

    result = job_functions.jobs_run("daily-briefing")

    assert result.status == ToolStatus.SUCCESS
    assert "Queued Daily Briefing as run #" in result.message
