from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import inspect, text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from dobby_app.config.settings import settings


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    from dobby_app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_lightweight_schema_updates()


def _ensure_lightweight_schema_updates() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        if "telegram_messages" in tables:
            existing = {column["name"] for column in inspector.get_columns("telegram_messages")}
            additions = {
                "reply_to_message_id": "INTEGER",
                "reply_to_text": "TEXT",
                "reply_to_kind": "VARCHAR(32)",
                "planner_batch_id": "VARCHAR(64)",
                "planner_processing_started_at": "DATETIME",
                "planner_processed_at": "DATETIME",
            }
            for column, column_type in additions.items():
                if column not in existing:
                    connection.execute(text(f"ALTER TABLE telegram_messages ADD COLUMN {column} {column_type}"))

        if "caldav_items" in tables:
            caldav_columns = {column["name"] for column in inspector.get_columns("caldav_items")}
            if "memory_page" not in caldav_columns:
                connection.execute(text("ALTER TABLE caldav_items ADD COLUMN memory_page TEXT"))
            old_column_name = "wi" + "ki_page"
            if old_column_name in caldav_columns:
                connection.execute(
                    text(f"UPDATE caldav_items SET memory_page = {old_column_name} WHERE memory_page IS NULL")
                )

        if "scheduled_jobs" in tables:
            from dobby_app.services.jobs import (
                DEFAULT_JOB_PROMPTS,
                PLANNER_PROMPT_JOB_TYPE,
                planner_prompt_for_seed,
            )

            old_job_type = "wi" + "ki_maintenance"
            connection.execute(
                text("UPDATE scheduled_jobs SET job_type = 'memory_maintenance' WHERE job_type = :old_job_type"),
                {"old_job_type": old_job_type},
            )
            for name, prompt in DEFAULT_JOB_PROMPTS.items():
                connection.execute(
                    text(
                        "UPDATE scheduled_jobs "
                        "SET prompt = :prompt "
                        "WHERE name = :name AND (prompt IS NULL OR trim(prompt) = '')"
                    ),
                    {"name": name, "prompt": planner_prompt_for_seed(name, prompt)},
                )
            empty_prompt_rows = connection.execute(
                text("SELECT name FROM scheduled_jobs WHERE prompt IS NULL OR trim(prompt) = ''")
            ).fetchall()
            for row in empty_prompt_rows:
                name = row[0]
                connection.execute(
                    text("UPDATE scheduled_jobs SET prompt = :prompt WHERE name = :name"),
                    {"name": name, "prompt": planner_prompt_for_seed(name, None)},
                )
            connection.execute(
                text(
                    "UPDATE scheduled_jobs "
                    "SET job_type = :job_type "
                    "WHERE job_type IN ('daily_briefing', 'memory_maintenance', 'telegram_reconciliation', 'generic') "
                    "OR job_type IS NULL OR trim(job_type) = ''"
                ),
                {"job_type": PLANNER_PROMPT_JOB_TYPE},
            )
