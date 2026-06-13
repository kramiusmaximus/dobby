from __future__ import annotations

from rq import Worker

from dobby_app.db.session import init_db
from dobby_app.config.logging import configure_logging
from dobby_app.integrations.queueing import default_queue, redis_conn


def main() -> None:
    configure_logging()
    init_db()
    worker = Worker([default_queue()], connection=redis_conn())
    worker.work()


if __name__ == "__main__":
    main()
