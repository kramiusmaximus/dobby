from __future__ import annotations

from sqlalchemy import desc
from sqlalchemy.orm import Session

from dobby_app.models import JobRun, ScheduledJob


def list_scheduled_jobs(session: Session) -> list[ScheduledJob]:
    return session.query(ScheduledJob).order_by(ScheduledJob.name).all()


def list_all_scheduled_jobs(session: Session) -> list[ScheduledJob]:
    return session.query(ScheduledJob).all()


def recent_job_runs(session: Session, limit: int = 10) -> list[JobRun]:
    return session.query(JobRun).order_by(desc(JobRun.id)).limit(limit).all()


def find_scheduled_job(session: Session, name: str) -> ScheduledJob:
    needle = name.strip()
    job = session.query(ScheduledJob).filter_by(name=needle).one_or_none()
    if not job:
        job = session.query(ScheduledJob).filter(ScheduledJob.name.like(f"%{needle}%")).first()
    if not job:
        raise ValueError(f"Job not found: {needle}")
    return job
