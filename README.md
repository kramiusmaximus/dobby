# DOBBY

DOBBY is Mark's VPS-hosted personal Telegram assistant and persistent Obsidian-style Markdown memory vault.

The project has been migrated from local/macOS automation toward a long-running Linux service. Telegram is the user interface; the durable center of the system is the Obsidian vault. Obsidian is DOBBY's source of truth for memory, including reminder and calendar context.

## Current Production Shape

DOBBY now runs on the VPS at `/opt/dobby` through Docker Compose:

- `poller`: Telegram polling intake, every 60 seconds.
- `app`: FastAPI service and health endpoint.
- `worker`: background job worker.
- `scheduler`: scheduled job process backed by PostgreSQL.
- `obsidian`: LinuxServer Obsidian desktop container with the production vault mounted.
- `postgres`: runtime state for jobs, queue history, Telegram records, and CalDAV item records.
- `redis`: queue backend.

The bot no longer requires a public Telegram webhook. The poller disables any existing webhook on startup and uses Telegram `getUpdates`.

## Persistent Memory

The previous Obsidian vault has been copied to the VPS at:

```text
/opt/dobby/wiki
```

The deployment workflow now preserves `/opt/dobby/wiki` across releases. Runtime memory operations should go through Obsidian Local REST API, backed by the synced vault.

Local vault path:

```text
wiki/
```

The vault includes:

- `.obsidian/` configuration.
- `index.md` and `log.md`.
- compiled memory pages under `wiki/pages/`.
- immutable source notes under `wiki/raw/sources/`.
- raw Telegram assets under `wiki/raw/assets/`.

## Telegram Commands

Registered bot commands:

```text
/status
/memory
/jobs
/queue
/today
/upcoming
/remind
/event
/job
```

Memory commands:

```text
/memory <query>
/memory save <durable note>
```

Calendar commands:

```text
/today
/upcoming
/remind Call dentist at tomorrow 9
/event Studio visit at Friday 15:00
```

Job commands:

```text
/jobs
/queue
/job show <name>
/job run <name>
/job pause <name>
/job resume <name>
/job schedule <name> every 2 hours
/job retry <run_id>
```

Plain text and voice messages without slash commands are routed through OpenAI using the model constants in `dobby_app/config.py`.

Every Telegram message should receive either a response, a failure reply with context, or a thumbs-up acknowledgement.

## Obsidian API

DOBBY memory queries and wiki writes use the Obsidian Local REST API plugin:

```env
OBSIDIAN_API_URL=http://127.0.0.1:27123
OBSIDIAN_API_KEY=
OBSIDIAN_VERIFY_TLS=false
OBSIDIAN_ENABLED=
```

`OBSIDIAN_ENABLED` can be left empty; DOBBY enables Obsidian automatically when `OBSIDIAN_API_KEY` is configured. Production uses the Local REST API plugin over localhost HTTP on port `27123`; HTTPS mode is intentionally disabled because the API is not exposed publicly.

The `obsidian` Compose service uses `lscr.io/linuxserver/obsidian:latest`, mounts the vault at `/config/dobby`, and persists the Obsidian desktop profile in `obsidian-config/`. `deployment/setup_obsidian_local_rest.py` installs/configures the plugin from the deployment host without committing plugin files or API keys.

## Calendar

DOBBY uses Obsidian as the source of truth for calendar and reminder context. iCloud Calendar over CalDAV is the production delivery and notification transport.

Reminder and event requests sync the relevant Obsidian wiki calendar page through the Obsidian API before writing to CalDAV.

Current VPS configuration:

- Main event calendar: `Личный`
- Reminder-style events: `Calendar`

The iCloud calendar named `Reminders ⚠️` is visible but rejects CalDAV writes with `403 Forbidden`, so DOBBY stores reminders as timed calendar events with alarms in a writable calendar.

## CI/CD

GitHub Actions runs:

- Ruff.
- pytest.
- Docker build.
- VPS deploy after successful `main` CI.

Deployment runs on the VPS self-hosted runner labeled `dobby-vps`. The deploy workflow preserves:

- `/opt/dobby/.env`
- `/opt/dobby/wiki`
- `/opt/dobby/obsidian-config`

See `deployment/README.md` for server setup and operational details.

## Local Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
```

Run locally with Docker:

```bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:8000/health
```
