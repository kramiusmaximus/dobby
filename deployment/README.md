# DOBBY VPS Deployment

This deployment runs DOBBY as three app services plus PostgreSQL and Redis:

- `app`: FastAPI Telegram webhook server.
- `poller`: Telegram long-polling intake loop.
- `worker`: RQ background worker.
- `scheduler`: APScheduler process that reads job schedules from PostgreSQL.
- `obsidian`: LinuxServer Obsidian desktop container with the DOBBY vault mounted at `/config/dobby`.
- `postgres`: durable runtime state.
- `redis`: queue backend.

## Server Setup

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

The Obsidian API is served by the Local REST API plugin on HTTP port `27123`. DOBBY containers use the Compose-internal URL `http://obsidian:27123`; the same port is also bound to `127.0.0.1` on the VPS for host diagnostics. HTTPS mode is disabled.

On a brand-new Obsidian profile, open the Obsidian GUI through an SSH tunnel to port `3001` and accept the vault author trust prompt once so community plugins can run. The trust decision is stored under `obsidian-config/`.

## Data To Preserve

The compose file mounts these folders into the app:

- `wiki/`
- `obsidian-config/`
- `assets/`
- `telegram_bot_cli/voice_messages/`
- `telegram_bot_cli/media_messages/`
- `data/automations/`

Back up PostgreSQL plus those folders daily.

## Job Control From Telegram

Supported commands:

```text
/jobs
/queue
/job show <name>
/job run <name>
/job pause <name>
/job resume <name>
/job schedule <name> every day at 8:30
/job schedule <name> Sundays at 11
/job schedule <name> every 2 hours
/job retry <run_id>
```

Reminder and event commands:

```text
/remind Call dentist at tomorrow 9
/event Studio visit at Friday 15:00
/today
/upcoming
```

Reminder and event writes update the Obsidian wiki calendar page through Obsidian Local REST API first, then write to CalDAV. Treat CalDAV as the notification transport and Obsidian as DOBBY's source of truth.

Plain text and transcribed voice messages are routed through the lightweight OpenAI router model configured by `ROUTER_MODEL`.

## Telegram Intake

DOBBY now uses Telegram polling by default, so no public HTTPS webhook is required. Configure these values in `/opt/dobby/.env`:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_USER_ID=
TELEGRAM_POLL_INTERVAL_SECONDS=60
```

The `poller` service disables any existing webhook and calls `getUpdates` every minute.

## GitHub CI/CD

The repository includes:

- `.github/workflows/ci.yml`: runs Ruff, pytest, and a Docker build.
- `.github/workflows/deploy.yml`: deploys successful `main` builds to the VPS.

The deploy workflow expects these repository secrets:

```text
none
```

The deploy job runs on the VPS through the `dobby-vps` GitHub self-hosted runner. It preserves `/opt/dobby/.env`, `/opt/dobby/wiki`, and `/opt/dobby/obsidian-config`, configures the Obsidian Local REST API plugin, rebuilds the DOBBY images, runs `docker compose up -d`, and checks `/health`.
