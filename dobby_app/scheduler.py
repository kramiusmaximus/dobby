from __future__ import annotations

from dobby_app.entrypoints.scheduler import main, sync_scheduler

__all__ = ["main", "sync_scheduler"]


if __name__ == "__main__":
    main()
