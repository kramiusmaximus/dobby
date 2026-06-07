# DOBBY

DOBBY is Mark's personal Telegram assistant and persistent Markdown wiki.

The current VPS app lives in `dobby_app/` and provides:

- Telegram webhook handling.
- OpenAI-backed routing for plain messages.
- CalDAV calendar events and calendar-based reminders.
- PostgreSQL-backed configurable jobs.
- Redis/RQ background execution.
- Docker Compose deployment.

See `deployment/README.md` for VPS setup.
