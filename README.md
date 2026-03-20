# oncall // shift tracker

Track oncall shifts via Slack slash commands. View shift history and stats through a REST API and web dashboard.

## Requirements

- Python 3.11+
- PostgreSQL

## Quick Start (Docker Compose)

```bash
docker compose up --build
```

This starts PostgreSQL, runs migrations, and launches the app on `http://localhost:8000`.

Set `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` in a `.env` file for Slack integration.

## Local Setup

```bash
pip install -e ".[dev]"
```

### Environment Variables

Create a `.env` file or export these:

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost/oncall
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
```

### Database

Create the database and run migrations:

```bash
createdb oncall
alembic upgrade head
```

### Start the Server

```bash
uvicorn oncall.main:app --reload
```

The dashboard is at `http://localhost:8000` and the API at `http://localhost:8000/api/`.

For Slack integration during local development, use [ngrok](https://ngrok.com) to expose the server and set your Slack app's slash command URLs to `https://<ngrok-url>/slack/events`.

## Slack Commands

| Command | Description |
|---|---|
| `/oncall` | Start an oncall shift |
| `/oncall-ticket <url>` | Log a GitHub issue to the active shift |
| `/offcall` | End the shift and post a summary to the channel |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Liveness check |
| GET | `/api/shifts` | List shifts (query: `user_id`, `limit`, `offset`) |
| GET | `/api/shifts/active` | Currently active shifts |
| GET | `/api/shifts/{id}` | Single shift with tickets |
| GET | `/api/stats` | Aggregate stats and per-user breakdown |

## Tests

```bash
pytest
```
