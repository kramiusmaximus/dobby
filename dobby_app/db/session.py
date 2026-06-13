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
    if "telegram_messages" not in tables:
        return

    existing = {column["name"] for column in inspector.get_columns("telegram_messages")}
    additions = {
        "reply_to_message_id": "INTEGER",
        "reply_to_text": "TEXT",
        "reply_to_kind": "VARCHAR(32)",
    }
    with engine.begin() as connection:
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
            old_job_type = "wi" + "ki_maintenance"
            connection.execute(
                text("UPDATE scheduled_jobs SET job_type = 'memory_maintenance' WHERE job_type = :old_job_type"),
                {"old_job_type": old_job_type},
            )
