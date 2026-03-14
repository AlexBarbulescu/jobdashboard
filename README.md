# Crypto Design Job Sentinel

Crypto Design Job Sentinel is a local-first dashboard for remote crypto and Web3 design roles. It runs as a Streamlit terminal-style dashboard backed by a Python refresh worker and a persistent SQLite data store.

## What it does

- Pulls jobs from crypto-focused RSS feeds and JSON-LD job pages.
- Filters for remote design roles only.
- Persists job state locally so Saved and Applied labels survive restarts.
- Auto-refreshes the UI and background ingestion loop for a live terminal feel.

## Local Docker workflow

1. Start the stack:

```bash
docker compose up --build
```

3. Open `http://localhost:8501`.

## Useful commands

Build and run:

```bash
docker compose up --build
```

Stop:

```bash
docker compose down
```

Stop and remove persistent job data:

```bash
docker compose down
```

PowerShell reset:

```powershell
Remove-Item .\data\jobs.db -ErrorAction SilentlyContinue
```

Follow worker logs:

```bash
docker compose logs -f worker
```

## Services

- `web`: Streamlit dashboard on port `8501`.
- `worker`: background refresh loop that ingests live sources on a schedule.

## Notes

- The first run triggers a source sync to seed the dashboard.
- If a source fails, the app stays up and the failure is surfaced in the Source Health lane.
- A ready-to-run `.env` is included for local startup, and `.env.example` is the template version.