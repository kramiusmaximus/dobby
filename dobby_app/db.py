from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import inspect, text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from dobby_app.config import settings


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
    from dobby_app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_lightweight_schema_updates()


def _ensure_lightweight_schema_updates() -> None:
    inspector = inspect(engine)
    if "telegram_messages" not in inspector.get_table_names():
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
