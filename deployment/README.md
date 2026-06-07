# DOBBY VPS Deployment

This deployment runs DOBBY as three app services plus PostgreSQL and Redis:

- `app`: FastAPI Telegram webhook server.
- `worker`: RQ background worker.
- `scheduler`: APScheduler process that reads job schedules from PostgreSQL.
- `postgres`: durable runtime state.
- `redis`: queue backend.

## Server Setup

```bash
apt update
apt install -y git docker.io docker-compose-plugin
systemctl enable --now docker
git clone git@github.com:kramiusmaximus/dobby.git /opt/dobby
cd /opt/dobby
cp .env.example .env
```

Fill `.env` with Telegram, OpenAI, and iCloud CalDAV credentials. For iCloud, use an app-specific password.

```bash
docker compose up -d --build
curl http://localhost:8000/health
curl -X POST http://localhost:8000/telegram/set-webhook
```

If there is no public HTTPS reverse proxy yet, run Telegram with long polling in a future worker mode or put Caddy/Nginx in front of port `8000`.

## Data To Preserve

The compose file mounts these folders into the app:

- `wiki/`
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

Plain text and transcribed voice messages are routed through the lightweight OpenAI router model configured by `ROUTER_MODEL`.
