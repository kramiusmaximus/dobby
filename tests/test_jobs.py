from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dobby_app.assistant.planner_runner import HandlerResponse
from dobby_app.db.models import JobRun, ScheduledJob
from dobby_app.db.session import Base
from dobby_app.workflows import jobs as job_workflow
from dobby_app.workflows.jobs import _execute_job, run_scheduled_job


def test_execute_job_runs_stored_prompt_through_planner(monkeypatch):
    sent = []
    captured = {}
    job = ScheduledJob(
        name="daily-briefing",
        display_name="Daily Briefing",
        enabled=True,
        schedule_text="every day at 9:00",
        cron={"hour": 9, "minute": 0},
        prompt="Brief Mark",
        job_type="planner_prompt",
    )

    async def fake_handle_plain_text_result(text, conversation_context=None):
        captured["text"] = text
        captured["conversation_context"] = conversation_context
        return HandlerResponse(text="Here is the briefing.")

    async def fake_send_telegram_message(text):
        sent.append(text)

    monkeypatch.setattr(job_workflow, "handle_plain_text_result", fake_handle_plain_text_result)
    monkeypatch.setattr(job_workflow, "send_telegram_message", fake_send_telegram_message)

    result = _execute_job(job)

    assert captured == {"text": "Brief Mark", "conversation_context": None}
    assert sent == ["Here is the briefing."]
    assert result == {
        "job_name": "daily-briefing",
        "job_type": "planner_prompt",
        "sent": True,
        "response_text": "Here is the briefing.",
        "reaction_emoji": None,
    }


def test_execute_job_does_not_send_reaction_only_response(monkeypatch):
    sent = []
    job = ScheduledJob(
        name="quiet-job",
        display_name="Quiet Job",
        enabled=True,
        schedule_text="every day at 9:00",
        cron={"hour": 9, "minute": 0},
        prompt="Do quiet maintenance",
        job_type="planner_prompt",
    )

    async def fake_handle_plain_text_result(text, conversation_context=None):
        return HandlerResponse(reaction_emoji="👍")

    async def fake_send_telegram_message(text):
        sent.append(text)

    monkeypatch.setattr(job_workflow, "handle_plain_text_result", fake_handle_plain_text_result)
    monkeypatch.setattr(job_workflow, "send_telegram_message", fake_send_telegram_message)

    result = _execute_job(job)

    assert sent == []
    assert result["sent"] is False
    assert result["reaction_emoji"] == "👍"


def test_execute_job_requires_prompt():
    job = ScheduledJob(
        name="empty-job",
        display_name="Empty Job",
        enabled=True,
        schedule_text="every day at 9:00",
        cron={"hour": 9, "minute": 0},
        prompt="",
        job_type="planner_prompt",
    )

    with pytest.raises(RuntimeError, match="has no planner prompt"):
        _execute_job(job)


def test_run_scheduled_job_marks_failed_runs(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    job = ScheduledJob(
        name="failing-job",
        display_name="Failing Job",
        enabled=True,
        schedule_text="every day at 9:00",
        cron={"hour": 9, "minute": 0},
        prompt="Fail",
        job_type="planner_prompt",
    )
    session.add(job)
    session.flush()
    run = JobRun(scheduled_job_id=job.id, status="queued")
    session.add(run)
    session.commit()

    monkeypatch.setattr(job_workflow, "SessionLocal", Session)
    monkeypatch.setattr(job_workflow, "_execute_job", lambda job: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        run_scheduled_job(job.id, run.id)

    session.expire_all()
    refreshed = session.get(JobRun, run.id)
    assert refreshed.status == "failed"
    assert refreshed.error == "boom"
    assert isinstance(refreshed.finished_at, datetime)
    session.close()
