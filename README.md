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

DOBBY's production vault lives at:

```text
/opt/dobby/wiki
```

The deployment workflow preserves `/opt/dobby/wiki` across releases. Runtime memory operations go through Obsidian Local REST API, backed by the synced vault.

Local vault path:

```text
wiki/
```

Local and VPS vaults are synced with Syncthing.

Synced folder:

```text
Folder ID: dobby-wiki
Local path: /Users/kramiusmaximus/projects/dobby/wiki
VPS path: /opt/dobby/wiki
```

Syncthing services:

```text
Mac: brew services start syncthing
VPS: systemctl status syncthing@root
```

Device IDs:

```text
Mac: 7EEVRLL-ER4XFPW-O2HEG46-QX4BETE-W3FAHHT-ETL3MZJ-TVKXZCC-ZRWB3AB
VPS: SBXCTYO-EJ2ZWDQ-EJ6OCKK-KSACMFL-6WXN752-2W2KNMA-HVDXKVB-DXXA4AB
```

Syncthing is configured as send/receive on both sides with permissions ignored for macOS/Linux compatibility. The current connection works through a Syncthing relay. For a direct connection, open TCP and UDP `22000` to the VPS in the provider firewall. The Syncthing GUI should stay bound to localhost; use an SSH tunnel if remote GUI access is needed.

Detailed wiki structure, memory policy, and assistant filing behavior live in `dobby_app/context/planner.md`.

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

Model constants:

```text
PLANNER_MODEL
PLANNER_REASONING_EFFORT
EXECUTOR_MODEL
EXECUTOR_REASONING_EFFORT
TRANSCRIPTION_MODEL
WIKI_MAINTENANCE_MODEL
DAILY_BRIEFING_MODEL
```

Planner and executioner startup logs include the configured model and reasoning effort. Defaults are `PLANNER_MODEL=gpt-5.5` with `PLANNER_REASONING_EFFORT=low`, and `EXECUTOR_MODEL=gpt-5.4-mini` with `EXECUTOR_REASONING_EFFORT=medium`.

Every Telegram message should receive either a response, a failure reply with context, or a thumbs-up acknowledgement.

Production Telegram intake is handled by the VPS `poller` service or webhook route. Runtime Telegram sends use `dobby_app.telegram_client`.

Telegram voice notes arrive as OGG/Opus files. The VPS app downloads voice files under the configured media root, converts unsupported audio formats to mp3 with `ffmpeg`, then calls OpenAI transcription using `TRANSCRIPTION_MODEL`.

## Obsidian API

DOBBY memory queries and wiki writes use the Obsidian Local REST API plugin:

```env
OBSIDIAN_API_URL=http://obsidian:27123
OBSIDIAN_API_KEY=
OBSIDIAN_VERIFY_TLS=false
OBSIDIAN_ENABLED=
```

`OBSIDIAN_ENABLED` can be left empty; DOBBY enables Obsidian automatically when `OBSIDIAN_API_KEY` is configured. Production uses the Local REST API plugin over Compose-internal HTTP at `http://obsidian:27123`; HTTPS mode is intentionally disabled because the API is not exposed publicly.

The `obsidian` Compose service uses `lscr.io/linuxserver/obsidian:latest`, publishes the API only on VPS loopback for host diagnostics, mounts the vault at `/config/dobby`, and persists the Obsidian desktop profile in `obsidian-config/`. `deployment/setup_obsidian_local_rest.py` installs/configures the plugin from the deployment host without committing plugin files or API keys.

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

Initial VPS setup:

```bash
apt update
apt install -y git docker.io docker-compose-v2
systemctl enable --now docker
git clone git@github.com:kramiusmaximus/dobby.git /opt/dobby
cd /opt/dobby
cp .env.example .env
```

Fill `.env` with Telegram, OpenAI, Obsidian Local REST API, and iCloud CalDAV credentials. For iCloud, use an app-specific password.

```bash
python3 deployment/setup_obsidian_local_rest.py /opt/dobby
docker compose up -d --build
curl http://localhost:8000/health
```

The Obsidian API is served by the Local REST API plugin on HTTP port `27123`. DOBBY containers use `http://obsidian:27123`; the same port is bound to `127.0.0.1` on the VPS for host diagnostics. HTTPS mode is disabled.

On a brand-new Obsidian profile, open the Obsidian GUI through an SSH tunnel to port `3001` and accept the vault author trust prompt once so community plugins can run. The trust decision is stored under `obsidian-config/`.

Deployment runs on the VPS self-hosted runner labeled `dobby-vps`. The deploy workflow preserves:

- `/opt/dobby/.env`
- `/opt/dobby/wiki`
- `/opt/dobby/obsidian-config`

The deploy workflow expects no repository secrets. It runs on the VPS through the `dobby-vps` self-hosted runner, configures the Obsidian Local REST API plugin, rebuilds DOBBY images, runs `docker compose up -d`, and checks `/health`.

VPS SSH target:

```text
ssh root@94.241.142.126
```

Local Codex credential file for this VPS:

```text
/Users/kramiusmaximus/.codex/secrets/dobby_vps.env
```

Do not commit plaintext VPS passwords or API secrets into this repository. Keep credentials in a local password manager, SSH agent, or environment file outside Git. The local Codex credential file should stay `chmod 600`.

Before changing deployment behavior, preserve runtime data:

- `/opt/dobby/.env`
- `/opt/dobby/wiki`
- `/opt/dobby/obsidian-config`
- `/opt/dobby/assets`
- `/opt/dobby/storage/media`
- `/opt/dobby/data/automations`
- PostgreSQL data volume
- Redis data volume when queue state matters

Back up PostgreSQL plus those folders daily.

## Runtime Context Templates

DOBBY's backend LLM behavior is guided by external Markdown templates:

- `dobby_app/context/planner.md`: planner policy for choosing `message`, `calendar`, and `wiki` actions.
- `dobby_app/context/tools/message.md`: message executioner prompt and tool contract.
- `dobby_app/context/tools/wiki.md`: wiki executioner prompt and tool contract.
- `dobby_app/context/tools/calendar.md`: calendar executioner prompt and tool contract.

Prefer updating these templates when changing natural-language assistant behavior. Keep Python responsible for validation, persistence, safe mutation, and integration boundaries.

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
