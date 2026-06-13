from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from dobby_app.db.session import session_scope
from dobby_app.db.models import CaldavItem

logger = logging.getLogger(__name__)


def stored_alarm_minutes_before(uid: str) -> int | None:
    try:
        with session_scope() as session:
            item = session.query(CaldavItem).filter_by(uid=uid).one_or_none()
            return item.alarm_minutes_before if item else None
    except SQLAlchemyError as exc:
        logger.warning("Could not read local CalDAV record for %s: %s", uid, exc)
        return None


def try_update_caldav_record(
    *,
    uid: str,
    title: str | None,
    item_type: str | None,
    starts_at: Any,
    duration_minutes: int | None,
    alarm_minutes_before: int | None,
    calendar_url: str,
    updated_at: Any,
) -> None:
    try:
        with session_scope() as session:
            item = session.query(CaldavItem).filter_by(uid=uid).one_or_none()
            if not item:
                return
            if title is not None:
                item.title = title
            if item_type is not None:
                item.item_type = item_type
            if starts_at is not None:
                item.starts_at = starts_at
                item.ends_at = starts_at
            if duration_minutes is not None:
                item.ends_at = (starts_at or item.starts_at) + timedelta(minutes=duration_minutes)
            if alarm_minutes_before is not None:
                item.alarm_minutes_before = alarm_minutes_before
            item.calendar_url = calendar_url
            item.updated_at = updated_at
    except SQLAlchemyError as exc:
        logger.warning("Could not update local CalDAV record for %s: %s", uid, exc)


def try_delete_caldav_record(uid: str) -> None:
    try:
        with session_scope() as session:
            item = session.query(CaldavItem).filter_by(uid=uid).one_or_none()
            if item:
                session.delete(item)
    except SQLAlchemyError as exc:
        logger.warning("Could not delete local CalDAV record for %s: %s", uid, exc)
