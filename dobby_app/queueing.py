from __future__ import annotations

from redis import Redis
from rq import Queue

from dobby_app.config import settings


def redis_conn() -> Redis:
    return Redis.from_url(settings.redis_url)


def default_queue() -> Queue:
    return Queue("dobby", connection=redis_conn())
