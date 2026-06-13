from __future__ import annotations

from dobby_app.entrypoints.poller import handle_update, main, poll_forever

__all__ = ["handle_update", "main", "poll_forever"]


if __name__ == "__main__":
    main()
