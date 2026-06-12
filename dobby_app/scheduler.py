from __future__ import annotations

import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from dobby_app.config import settings
from dobby_app.db import SessionLocal, init_db
from dobby_app.jobs import enqueue_job
from dobby_app.logging_config import configure_logging
from dobby_app.models import ScheduledJob
from dobby_app.schedules import cron_trigger
from dobby_app.seed import seed_default_jobs


def sync_scheduler(scheduler: BackgroundScheduler) -> None:
    with SessionLocal() as session:
        seed_default_jobs(session)
        session.commit()
        jobs = session.query(ScheduledJob).all()
        desired_ids = set()
        for job in jobs:
            scheduler_id = f"scheduled-{job.id}"
            desired_ids.add(scheduler_id)
            if not job.enabled:
                if scheduler.get_job(scheduler_id):
                    scheduler.remove_job(scheduler_id)
                continue
            trigger = cron_trigger(job.cron, settings.app_timezone)
            existing = scheduler.get_job(scheduler_id)
            if existing:
                existing.reschedule(trigger)
            else:
                scheduler.add_job(_queue_scheduled_job, trigger=trigger, id=scheduler_id, args=[job.id])
            next_run = scheduler.get_job(scheduler_id).next_run_time
            job.next_run_at = next_run
            job.updated_at = datetime.utcnow()

        for existing in scheduler.get_jobs():
            if existing.id.startswith("scheduled-") and existing.id not in desired_ids:
                scheduler.remove_job(existing.id)
        session.commit()


def _queue_scheduled_job(job_id: int) -> None:
    with SessionLocal() as session:
        job = session.get(ScheduledJob, job_id)
        if job and job.enabled:
            enqueue_job(session, job)
            session.commit()


def main() -> None:
    configure_logging()
    init_db()
    scheduler = BackgroundScheduler(timezone=settings.app_timezone)
    scheduler.start()
    while True:
        sync_scheduler(scheduler)
        time.sleep(30)


if __name__ == "__main__":
    main()
